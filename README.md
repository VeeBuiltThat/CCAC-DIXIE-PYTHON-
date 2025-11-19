# CCAC-DIXIE-PYTHON- (Discord Moderation Bot)

Discord moderation bot used by CCAC. This repository contains the bot entrypoint, database helpers, and a set of moderation cogs (extensions) for warnings, blacklist handling, audit logs, anti-forward protection, slowmode, link-snatching, and more.

## Quick links (workspace)
- [main.py](main.py) — bot entrypoint and cog loader
- [`verification.Security`](verification.py) — verification cog (verify flow, DM resend)
- [`dbconn.create_table`](dbconn.py) — verification user DB setup
- [`dbconnMOD.create_mod_log_table`](dbconnMOD.py) — mod logs DB setup
- [dbconn.py](dbconn.py) — verification DB helper
- [dbconnMOD.py](dbconnMOD.py) — moderation DB helper
- [modlogs.py](modlogs.py) — simple mod-logs example
- cogs/ — all bot cogs:
  - [cogs/mod.py](cogs/mod.py)
  - [cogs/verification.py](verification.py) (loaded as a Cog via [`verification.Security`](verification.py))
  - [cogs/budget.py](cogs/budget.py)
  - [cogs/link_snatcher.py](cogs/link_snatcher.py)
  - [cogs/slowmode.py](cogs/slowmode.py)
  - [cogs/blacklist.py](cogs/blacklist.py)
  - [cogs/blacklist_filter.py](cogs/blacklist_filter.py)
  - [cogs/anti_forward.py](cogs/anti_forward.py)
  - [cogs/auditlogs.py](cogs/auditlogs.py)
  - [cogs/botdetection.py](cogs/botdetection.py)

## Prerequisites
- Python 3.10+ (recommended)
- MySQL server accessible with credentials in .env
- Discord bot token and required role/channel IDs in .env

Install dependencies:
```sh
pip install -r requirements.txt
```

## Environment (.env)
Create a .env file at the repo root containing at least:
- DISCORD_TOKEN=<your bot token>
- MOD_HOST, MOD_PORT, MOD_USER, MOD_PASSWORD, MOD_DATABASE — MySQL for moderation tables
- DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME — used by some cogs (slowmode)
- Various role/channel IDs used by cogs (see `verification.py`, `cogs/config.py`, `cogs/mod.py`)

Key env-vars referenced:
- [`verification.py`] expects: REQUIRED_ROLE_ID, UNVERIFIED_ROLE_ID, WELCOME_CHANNEL_ID, NOTICE_CHANNEL_ID, GUILD_ID, NOTICE_MESSAGE, STAFF_CONTACT_CHANNEL
- [`dbconn.py`] / [`dbconnMOD.py`] expect MOD_HOST / MOD_PORT / MOD_USER / MOD_PASSWORD / MOD_DATABASE

## Database setup
The bot calls database table creation on startup:
- Verification table: [`dbconn.create_table`](dbconn.py) — called from [main.py](main.py)
- Mod-logs table: [`dbconnMOD.create_mod_log_table`](dbconnMOD.py) — called from [main.py](main.py)
You can also run the helper modules manually to ensure tables exist.

## Running the bot
Start the bot with:
```sh
python main.py
```
`main.py` will:
- create DB tables via [`dbconn.create_table`](dbconn.py) and [`dbconnMOD.create_mod_log_table`](dbconnMOD.py)
- load cogs from the cogs/ folder
- add the verification cog class [`verification.Security`](verification.py)

Note: `main.py` also attempts to start a ModMail bot at `Modmail-master-1/bot.py` (see code).

## Common commands (where implemented)
- Verification:
  - !verify <password> — [`verification.Security.verify`](verification.py)
  - !dmme — [`verification.Security.dm_me`](verification.py)
  - !DMuser <user> — [`verification.Security.dm_user`](verification.py)
- Moderation (cogs/mod.py):
  - !ban, !kick, !timeout, !wminor, !wmajor, !wremoveminor, !wremovemajor, !whois
  - Uses [`dbconnMOD.add_mod_log`](dbconnMOD.py) to record actions
- Budget detection (cogs/budget.py) — automated checks + warning UI
- Blacklist (cogs/blacklist.py) — !blacklist, !blacklistcheck
- Link snatcher (cogs/link_snatcher.py) — deletes links in restricted channels
- Slowmode (cogs/slowmode.py) — per-channel custom slowmode stored in MySQL

## Notes & maintenance
- Secrets must remain in .env (see [.gitignore](.gitignore)).
- Many cogs expect specific role/channel IDs; verify values in environment or in [cogs/config.py](cogs/config.py).
- Database connection functions are in [`dbconn.py`](dbconn.py) and [`dbconnMOD.py`](dbconnMOD.py). Use them for migrations or manual checks.
- Logs and debugging print statements are used in DB helpers (see [modlogs.py](modlogs.py), [dbconnMOD.py](dbconnMOD.py)).

## Contributing
- Add new cogs to the cogs/ folder and ensure they expose async setup(bot) handlers (pattern used in cogs).
- Keep secrets out of git. Use .env or a secret manager.

## Troubleshooting
- "Bot token not found" — ensure DISCORD_TOKEN in .env.
- DB connection errors — verify MOD_* env vars and that MySQL accepts remote connections.
- Permissions issues — the bot needs Manage Roles, Kick/Ban, Manage Messages, Send Messages, Embed Links, etc.
