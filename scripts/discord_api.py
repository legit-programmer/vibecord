#!/usr/bin/env python3
"""Minimal Discord REST API helper for the vibecord skill (stdlib only).

Usage:
  python discord_api.py check
  python discord_api.py request METHOD PATH [--json '{"k":"v"}' | --json-file body.json] [--query k=v ...] [--reason TEXT]

PATH is relative to https://discord.com/api/v10, e.g. /users/@me/guilds
The token is read from the environment and is never printed.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/legit-programmer/vibecord, 1.0)"
ENV_NAMES = ("discord_bot_token", "DISCORD_BOT_TOKEN")

# Exit codes
EXIT_NO_TOKEN = 2
EXIT_BAD_TOKEN = 3
EXIT_HTTP_ERROR = 4


def _windows_user_env(name):
    """Read a persisted user/system env var (set via setx or System Properties)
    that the current process may not see yet because it was started earlier."""
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    locations = [
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ]
    for hive, path in locations:
        try:
            with winreg.OpenKey(hive, path) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value:
                    return str(value)
        except OSError:
            continue
    return None


def get_token():
    for name in ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            return value, f"process env ({name})"
    for name in ENV_NAMES:
        value = (_windows_user_env(name) or "").strip()
        if value:
            return value, f"Windows persisted env ({name})"
    return None, None


def _strip_prefix(token):
    return token[4:].strip() if token.lower().startswith("bot ") else token


_TOP_LEVEL = ("applications", "channels", "guilds", "users", "webhooks", "invites",
              "stickers", "sticker-packs", "gateway", "oauth2", "voice",
              "stage-instances", "interactions", "lobbies", "soundboard-default-sounds")


def _undo_msys_path(path):
    """Git Bash (MSYS) rewrites '/users/@me' into 'C:/Program Files/Git/users/@me'.
    Recover the original Discord path from such a converted argument."""
    p = path.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", p):
        parts = p.split("/")
        for i, seg in enumerate(parts):
            if seg in _TOP_LEVEL:
                return "/" + "/".join(parts[i:])
    return path


def call(method, path, body=None, query=None, reason=None, max_retries=3):
    token, _ = get_token()
    if not token:
        print(json.dumps({"error": "missing_token", "checked": list(ENV_NAMES)}))
        sys.exit(EXIT_NO_TOKEN)

    path = _undo_msys_path(path)
    if not path.startswith("/"):
        path = "/" + path
    url = API_BASE + path
    if query:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query)

    headers = {
        "Authorization": "Bot " + _strip_prefix(token),
        "User-Agent": USER_AGENT,
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if reason:
        headers["X-Audit-Log-Reason"] = urllib.parse.quote(reason)

    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                payload = {"raw": raw}
            if e.code == 429 and attempt < max_retries:
                wait = float((payload or {}).get("retry_after", 1.0))
                time.sleep(min(wait, 30) + 0.25)
                continue
            return e.code, payload
        except urllib.error.URLError as e:
            return 0, {"error": "network_error", "detail": str(e.reason)}
    return 429, {"error": "rate_limited", "detail": "retries exhausted"}


def cmd_check(_args):
    token, source = get_token()
    if not token:
        print(json.dumps({"ok": False, "error": "missing_token", "checked": list(ENV_NAMES)}))
        sys.exit(EXIT_NO_TOKEN)
    status, payload = call("GET", "/users/@me")
    if status != 200:
        print(json.dumps({"ok": False, "error": "token_rejected", "status": status, "response": payload, "source": source}))
        sys.exit(EXIT_BAD_TOKEN)
    print(json.dumps({
        "ok": True,
        "source": source,
        "bot": {"id": payload.get("id"), "username": payload.get("username"), "bot": payload.get("bot")},
    }, indent=2))


def cmd_request(args):
    body = None
    if args.json is not None:
        body = json.loads(args.json)
    elif args.json_file:
        with open(args.json_file, "r", encoding="utf-8") as f:
            body = json.load(f)
    query = dict(q.split("=", 1) for q in (args.query or []))
    status, payload = call(args.method, args.path, body=body, query=query or None, reason=args.reason)
    print(json.dumps({"status": status, "data": payload}, indent=2, ensure_ascii=False))
    if status == 0 or status >= 400:
        sys.exit(EXIT_HTTP_ERROR)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="Verify the token exists and is accepted by Discord")

    r = sub.add_parser("request", help="Call any Discord REST endpoint")
    r.add_argument("method", help="GET, POST, PATCH, PUT, DELETE")
    r.add_argument("path", help="Endpoint path, e.g. /channels/123/messages")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--json", help="JSON request body as a string")
    g.add_argument("--json-file", help="Path to a JSON file used as the request body")
    r.add_argument("--query", action="append", help="Query param k=v (repeatable)")
    r.add_argument("--reason", help="Audit log reason (X-Audit-Log-Reason)")

    args = parser.parse_args()
    {"check": cmd_check, "request": cmd_request}[args.cmd](args)


if __name__ == "__main__":
    main()
