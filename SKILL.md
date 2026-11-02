---
name: vibecord
description: "Control a Discord bot through the Discord REST API using a bot token from the `discord_bot_token` environment variable. Send/edit/delete messages, list guilds/channels/members/roles, manage channels, roles, reactions, threads, webhooks, and anything else the bot is permitted to do. Trigger when the user invokes /vibecord, or asks to do something on Discord via their bot."
---

# `/vibecord` — drive a Discord bot with plain-language instructions

The user describes what they want ("post 'deploy done' in #general", "list my servers",
"give @alice the Mod role") and you translate it into Discord REST API calls made with
their bot token.

Helper script (stdlib Python, no installs needed):

```
python "<skill base dir>/scripts/discord_api.py" check
python "<skill base dir>/scripts/discord_api.py" request METHOD PATH [--json '{...}' | --json-file body.json] [--query k=v ...] [--reason TEXT]
```

- `PATH` is relative to `https://discord.com/api/v10` (e.g. `/users/@me/guilds`).
- Output is JSON: `{"status": <http code>, "data": <response>}`.
- Exit codes: `0` ok, `2` token missing, `3` token rejected, `4` HTTP/network error.
- `<skill base dir>` is the directory this SKILL.md lives in (given when the skill loads).
- 429 rate limits are retried automatically.
- Git Bash on Windows rewrites arguments like `/users/@me` into Windows paths; the
  script undoes this automatically, or you can omit the leading slash (`users/@me`).
- For bodies with quotes/newlines/non-ASCII, write the body to a file in the scratchpad
  and use `--json-file` instead of `--json` (avoids shell quoting problems on Windows).

## Step 1 — ALWAYS run the token check first

Run `check` at the start of every `/vibecord` session before any other call.

The script looks for the token in this order and never prints it:
1. Process env `discord_bot_token`, then `DISCORD_BOT_TOKEN`.
2. On Windows, the persisted user/system env (registry) — so a token set with `setx`
   works even if this terminal was opened before it was set.

### If `check` reports `missing_token` (exit 2) — stop and give the user setup instructions

Do not attempt any API call. Show the user these steps:

1. **Create the application** — go to <https://discord.com/developers/applications>,
   click **New Application**, name it, accept the terms.
2. **Get the bot token** — open the **Bot** tab → **Reset Token** → confirm → **Copy**.
   The token is shown only once. Treat it like a password: never commit it or paste it
   in chat.
3. **Enable privileged intents if needed** (same Bot tab): *Server Members Intent* for
   member lists, *Message Content Intent* for reading message text.
4. **Invite the bot to a server** — **OAuth2 → URL Generator** → scopes `bot` (and
   `applications.commands` if slash commands are wanted) → pick bot permissions
   (e.g. *Send Messages, Read Message History, Manage Messages, Manage Channels,
   Manage Roles*, or *Administrator* for a private test server) → open the generated
   URL and add it to a server you manage.
5. **Set the environment variable** (pick the user's shell):
   - Windows PowerShell (persistent): `setx discord_bot_token "PASTE_TOKEN_HERE"`
   - Windows PowerShell (current session only): `$env:discord_bot_token = "PASTE_TOKEN_HERE"`
   - macOS/Linux (bash/zsh): add `export discord_bot_token="PASTE_TOKEN_HERE"` to
     `~/.bashrc` / `~/.zshrc`, then `source` it.
6. **Restart Claude Code** (or open a new terminal) so the variable is picked up, then
   run `/vibecord` again.

Tell the user to set the variable themselves in their own terminal — never ask them to
paste the token into the conversation. If they paste it anyway, don't echo it back, and
recommend they reset it in the Developer Portal.

### If `check` reports `token_rejected` (exit 3)

Status 401 means the token is invalid or was reset — tell the user to reset it on the Bot
tab and update the env var. Show the status and Discord's error message, never the token.

### If `check` succeeds

Briefly confirm which bot is connected (username + id), then proceed with the request.

## Step 2 — carry out the user's instruction

1. **Resolve names to IDs.** Users say "#general" or "my test server"; the API needs
   snowflake IDs. Discover them:
   - Servers: `GET /users/@me/guilds`
   - Channels: `GET /guilds/{guild_id}/channels` (type 0 = text, 2 = voice, 4 = category, 5 = announcement, 15 = forum)
   - Roles: `GET /guilds/{guild_id}/roles`
   - Members: `GET /guilds/{guild_id}/members/search --query query=alice --query limit=10`
     (or `GET /guilds/{guild_id}/members --query limit=100`; needs Server Members Intent)
   If a name matches multiple things, or the bot is in multiple servers and it's unclear
   which one, ask the user.
2. **Make the call(s)** with the helper.
3. **Report the result** concisely (e.g. message link
   `https://discord.com/channels/{guild_id}/{channel_id}/{message_id}`, counts, names).
   Summarize large responses instead of dumping raw JSON.

## Safety rules

- **Confirm before destructive or broad actions**: deleting messages/channels/roles,
  bulk delete, kicks, bans, timeouts, permission overwrites, role changes on many
  members, deleting webhooks, leaving a guild. State exactly what will be affected first.
- Sending a message is visible to others — if the target channel or text is ambiguous,
  confirm first. Otherwise just send.
- Pass `--reason` on moderation/admin actions so they show in the audit log.
- Never print, log, or write the token to files.
- Don't loop over many members/channels faster than needed; the script retries 429s but
  avoid mass actions unless the user explicitly asks.

## Common endpoint cheat sheet

| Task | Call |
|---|---|
| Bot identity | `GET /users/@me` |
| List servers | `GET /users/@me/guilds` |
| Server info | `GET /guilds/{guild_id} --query with_counts=true` |
| List channels | `GET /guilds/{guild_id}/channels` |
| Send message | `POST /channels/{channel_id}/messages --json '{"content":"hi"}'` |
| Send embed | `POST /channels/{channel_id}/messages` body `{"embeds":[{"title":"..","description":"..","color":5814783}]}` |
| Reply | body `{"content":"..","message_reference":{"message_id":"ID"}}` |
| Read messages | `GET /channels/{channel_id}/messages --query limit=50` (content needs Message Content Intent) |
| Edit message | `PATCH /channels/{channel_id}/messages/{message_id}` |
| Delete message | `DELETE /channels/{channel_id}/messages/{message_id}` |
| Bulk delete (2–100, <14 days old) | `POST /channels/{channel_id}/messages/bulk-delete` body `{"messages":[ids]}` |
| Pin / unpin | `PUT` / `DELETE /channels/{channel_id}/pins/{message_id}` |
| Add reaction | `PUT /channels/{channel_id}/messages/{message_id}/reactions/{url-encoded emoji}/@me` |
| Create channel | `POST /guilds/{guild_id}/channels` body `{"name":"x","type":0,"parent_id":"cat_id"}` |
| Edit channel | `PATCH /channels/{channel_id}` |
| Delete channel | `DELETE /channels/{channel_id}` |
| Create thread from message | `POST /channels/{channel_id}/messages/{message_id}/threads` body `{"name":"x"}` |
| Create role | `POST /guilds/{guild_id}/roles` body `{"name":"x","color":0,"hoist":false}` |
| Add / remove role | `PUT` / `DELETE /guilds/{guild_id}/members/{user_id}/roles/{role_id}` |
| Change nickname | `PATCH /guilds/{guild_id}/members/{user_id}` body `{"nick":"x"}` |
| Timeout member | `PATCH /guilds/{guild_id}/members/{user_id}` body `{"communication_disabled_until":"ISO8601"}` |
| Kick | `DELETE /guilds/{guild_id}/members/{user_id}` |
| Ban / unban | `PUT` / `DELETE /guilds/{guild_id}/bans/{user_id}` |
| DM a user | `POST /users/@me/channels` body `{"recipient_id":"ID"}` → then send to returned channel id |
| Webhooks | `GET/POST /channels/{channel_id}/webhooks` |
| Scheduled events | `GET/POST /guilds/{guild_id}/scheduled-events` |
| Slash commands (global) | `GET/POST /applications/{application_id}/commands` (application id = bot user id) |
| Audit log | `GET /guilds/{guild_id}/audit-logs --query limit=50` |

For anything not listed, use the official docs at
<https://discord.com/developers/docs/reference> and call the endpoint with `request`.

## Limits of this skill

This uses the REST API only. Anything that needs a live Gateway (WebSocket)
connection — staying online with a green status, listening for new messages/events in
real time, voice — is out of scope. If the user wants that, offer to scaffold a small
bot project (e.g. discord.js or discord.py) instead.

## Common errors

- `401 Unauthorized` — bad/reset token → see Step 1.
- `403 Missing Access` / `50001` — bot isn't in that server or can't see the channel.
- `403 Missing Permissions` / `50013` — bot lacks the permission, or its role is below
  the target role/member in the role list.
- `404 Unknown Channel/Guild/Message` — wrong ID, or the bot can't see it.
- `50035 Invalid Form Body` — check the body fields in the response's `errors` object.
