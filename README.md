# vibecord

A Claude Code skill that lets you control your Discord bot in plain language.

```
/vibecord list my servers
/vibecord post "deploy done" in #general
/vibecord give @alice the Mod role
```

Claude turns your request into Discord REST API calls made with your bot token.

## Install

```bash
npx skills add legit-programmer/vibecord
```

Or copy this folder to `~/.claude/skills/vibecord`.

## Setup

1. Create an application at <https://discord.com/developers/applications>.
2. On the **Bot** tab, click **Reset Token** and copy it.
3. Invite the bot to your server: **OAuth2 → URL Generator**, scope `bot`, pick permissions.
4. Set the token as an environment variable:
   - Windows: `setx discord_bot_token "YOUR_TOKEN"`
   - macOS/Linux: `export discord_bot_token="YOUR_TOKEN"`

If the token is missing, the skill walks you through these steps on first run.

## Requirements

- Python 3 (standard library only)

## Notes

- Your token stays in your environment. The skill never prints it or writes it to a file.
- Claude asks before deleting things, kicking, banning, or making bulk changes.
- REST API only: it can't keep the bot online or listen for live events.
