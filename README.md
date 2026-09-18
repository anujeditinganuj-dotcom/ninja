# BotControl Manager

A production-ready Telegram bot management system. One **Master Control Bot**
lets an owner (and optionally extra admins) connect and independently manage
**multiple** Telegram bots — each with its own start message, welcome photo,
inline buttons, and maintenance mode.

## Features

- Connect unlimited Telegram bots through one Master Control Bot
- Per-bot custom **Normal** and **Maintenance** start messages (text, Markdown/HTML, emoji)
- Per-bot **welcome photo** support, stored by Telegram `file_id` (no local downloads)
- Per-bot inline buttons (multi-row)
- Per-bot maintenance mode toggle — switches the `/start` response instantly
- `/mybots`-style bot list, live preview, and per-bot statistics (users, starts, connected date)
- **Broadcast** — message every user of a specific bot, with FloodWait-safe rate limiting.
  Usable from a bot's own panel, or directly via `/broadcast` (picks the bot for you).
- **Ban / Unban** — silently block a user of a specific bot. Also available directly
  via `/ban` and `/unban`, same bot-picker shortcut.
- **Force-Subscribe** — require users to join a channel before a bot's `/start` message is shown
- **Export Users** — download a bot's user list as CSV
- **Backup & Restore** — export all bot configs to JSON and restore them with `/restore`
- **Combined statistics** — total users/starts across every connected bot, not just per-bot
- **Multi-admin access** — the real `OWNER_ID` can grant additional Telegram
  user IDs admin rights (Settings → Admin → Admin Access) so they can run
  bot-operation features (broadcast, ban, messages, connect) without sharing
  the owner's own account. Settings itself always stays owner-only.
- **Full Settings menu** — Bot Management (auto-reconnect, auto-start-on-boot,
  default status for newly connected bots), Notifications (error/offline
  alerts, a daily stats digest), Security (token-encryption status, an
  access-control switch for destructive actions, an activity log of every
  admin action), and Database (live MongoDB connection status and storage info)
- Bot tokens encrypted at rest (Fernet) whenever `ENCRYPTION_KEY` is set —
  Settings → Security shows you plainly if it currently isn't
- Each managed bot runs as an independent async client — one bot crashing or
  being disconnected never affects the Master Bot or any other managed bot
- Automatic startup recovery: all enabled bots reconnect from MongoDB after a
  restart (toggle: Settings → Bot Management → Auto Start Bots), and a
  watchdog restarts a bot that drops mid-session (toggle: Auto Reconnect)
- Self-ping **keep-alive** so free-tier hosts (Render, etc.) don't spin the app down when idle
- `/cancel` on every multi-step flow
- Docker, systemd, and Render-ready

## Requirements

- Python 3.11+
- A MongoDB instance (Atlas or self-hosted)
- A Telegram API ID/Hash (from https://my.telegram.org)
- A Master Bot token from @BotFather

## 1. BotFather setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow the prompts.
2. Save the token it gives you as `BOT_TOKEN`.
3. Repeat `/newbot` for each bot you want to manage later — you'll connect
   those tokens from inside the Master Bot itself, not in `.env`.

## 2. Telegram API setup

1. Go to https://my.telegram.org → **API Development Tools**.
2. Create an app and copy `api_id` and `api_hash` into `.env` as `API_ID` / `API_HASH`.

## 3. MongoDB setup

- Local: `mongodb://localhost:27017`
- Atlas: create a free cluster, add a database user, allow your IP, and copy
  the connection string into `MONGO_URI`.

## 4. Environment configuration

```bash
cp .env.example .env
```

Fill in:

```
API_ID=1234567
API_HASH=your_api_hash
BOT_TOKEN=123456:your_bot_token
OWNER_ID=123456789          # your numeric Telegram user ID (e.g. via @userinfobot)
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=botcontrol
PORT=8080
ENCRYPTION_KEY=             # generate below
MAINTENANCE_REMINDER_HOURS=24
```

Generate an encryption key so bot tokens are stored encrypted:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> ⚠️ **Never hardcode real secrets as defaults in `config.py`.** `config.py`
> should only ever contain placeholder fallbacks (e.g. `"your_bot_token"`) —
> your actual token, Mongo URI, and encryption key belong in `.env` only,
> which is git-ignored. If a real secret ever ends up committed or shared
> (in `config.py`, a screenshot, a support chat, etc.), treat it as
> compromised: revoke the bot token via `/revoke` in @BotFather, rotate the
> MongoDB user's password, and generate a fresh `ENCRYPTION_KEY` — note that
> rotating the key means previously-encrypted bot tokens in the database
> won't decrypt anymore, so you'll need to reconnect those bots with fresh
> tokens afterwards.

Never commit `.env` — it's already in `.gitignore`.

## 5. Local installation

```bash
git clone <repository>
cd botcontrol

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

nano .env   # fill in your values

python3 main.py
```

## 6. VPS deployment (systemd)

```bash
sudo useradd -r -s /bin/false botcontrol
sudo mkdir -p /opt/botcontrol /var/log/botcontrol
sudo cp -r . /opt/botcontrol
cd /opt/botcontrol
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt
sudo nano .env
sudo chown -R botcontrol:botcontrol /opt/botcontrol /var/log/botcontrol

sudo cp botcontrol.service /etc/systemd/system/botcontrol.service
sudo systemctl daemon-reload
sudo systemctl enable botcontrol
sudo systemctl start botcontrol
sudo systemctl status botcontrol
```

The service restarts automatically on failure and on VPS reboot, and loads
`.env` via `EnvironmentFile`.

## 7. Docker deployment

```bash
docker build -t botcontrol .
docker run -d --name botcontrol --env-file .env -p 8080:8080 --restart unless-stopped botcontrol
```

## 8. Render deployment

**Option A — One-click Blueprint (recommended)**

This repo includes `render.yaml`. On Render: **New → Blueprint** → connect
the repo → Render reads `render.yaml` and creates the Web Service for you.
Fill in the secret env vars it asks for (`API_ID`, `API_HASH`,
`BOT_TOKEN`, `OWNER_ID`, `MONGO_URI`, `ENCRYPTION_KEY`) and deploy.
`PORT` is injected by Render automatically — never set it yourself.

**Option B — Manual Web Service**

1. Push this repo to GitHub.
2. On Render: **New → Web Service** → connect the repo.
3. Environment: **Docker** (uses the included `Dockerfile`) — or, for a
   native build, set build command `pip install -r requirements.txt` and
   start command `python3 main.py`.
4. Add all `.env` variables under **Environment** (skip `PORT`).
5. Render sets `PORT` automatically — the app's health server binds to it,
   and Pyrogram's polling runs in the same process, so no duplicate pollers
   are ever started for the same bot.

## Commands

| Command | What it does |
|---|---|
| `/start` | Opens the main dashboard |
| `/help` | Shows the full feature list |
| `/connect` | Connects a new bot by token |
| `/mybots` | Lists connected bots and opens their panels |
| `/stats` | Combined statistics across every bot |
| `/broadcast` | Pick a bot, then broadcast a message to its users |
| `/ban` / `/unban` | Pick a bot, then ban/unban a user of it |
| `/settings` | Opens the Settings menu (owner-only) |
| `/restore` | Restore bots from a backup JSON file |
| `/cancel` | Aborts whatever multi-step flow is in progress |

## How to connect a managed bot

1. Open the Master Bot, send `/start`.
2. Tap **➕ Connect Bot**.
3. Send the bot token from @BotFather.
4. Review the detected name/username/ID, tap **✅ Confirm**.
5. The bot is saved to MongoDB. It stays offline until you turn on either
   **🛠 Maintenance** or **🚀 Go Live**, so it never conflicts with a bot
   host you're already running elsewhere with the same token.

## How to enable maintenance

1. `/mybots` → pick the bot → **🛠 Maintenance** → **🟢 Enable** / **🔴 Disable**.
2. Users who message that bot instantly get the maintenance message until
   you disable it again.
3. If you leave Maintenance ON for a while, the owner gets a periodic
   reminder (interval set by `MAINTENANCE_REMINDER_HOURS`) — it's just a
   nudge, the bot does **not** turn itself off automatically.

## How to set custom messages

1. Pick the bot → **✏️ Edit Message** → choose **Normal** or **Maintenance**.
2. Send text, or a photo/video/document/animation with a caption.
3. The message is saved against that bot's ID only — other bots are untouched.

To only change the welcome image without touching the text, use
**🖼 Edit Welcome Photo** instead — but set the text first via **Edit Message**
if it isn't right yet, since the photo step reuses whatever text/caption is
already saved as the new photo's caption.

## How to add buttons

1. Pick the bot → **🔘 Buttons** → send the button label, then its URL.
2. Repeat to add more buttons (each addition starts a new row).

## Settings menu (owner-only)

`/settings` or the **⚙️ Settings** button on the dashboard opens:

- **👤 Admin** — shows the real `OWNER_ID`, and **Admin Access** to add or
  remove additional Telegram user IDs as admins. Added admins can use
  broadcast, ban/unban, messages, connect, and stats — but never Settings
  itself, and (by default) not disconnect a bot or restore a backup either.
- **🤖 Bot Management** — toggle **Auto Reconnect** (watchdog auto-restart
  for a dropped bot), **Auto Start Bots** (reconnect eligible bots on
  process boot), and the **Default** maintenance status for newly connected bots.
- **🔔 Notifications** — toggle **Error Alerts**, **Bot Offline Alerts**, and
  a **Daily Statistics** digest sent once every 24 hours.
- **🔐 Security** — see whether **Token Protection** (`ENCRYPTION_KEY`) is
  active, toggle **Access Control** (when ON, only the real owner — not
  added admins — can disconnect a bot, restore a backup, or manage admins),
  and view the **Activity Logs** of recent admin actions.
- **🗄️ Database** — **Database Status** (live MongoDB ping + collection
  counts) and **Data Information** (storage size, document counts via
  MongoDB's `dbStats`).

### How to add an admin

1. `/settings` → **👤 Admin** → **🔐 Admin Access** → **➕ Add Admin**.
2. Send their numeric Telegram user ID (ask them to send `/start` to
   [@userinfobot](https://t.me/userinfobot) to get it).
3. They can now message the Master Bot and use every bot-operation feature.

## Troubleshooting

| Problem | Cause / fix |
|---|---|
| `❌ Invalid bot token` | Token was mistyped, revoked, or already connected — request a fresh one from @BotFather. |
| `TelegramConflictError` | Another process is already polling the same bot token. Make sure only one instance of `main.py` (or one Docker/Render deployment) is running. |
| Bot shows offline in **My Bots** | Check `MONGO_URI` connectivity and the app logs; the watchdog auto-restarts a bot whose client stops responding — unless **Auto Reconnect** is turned OFF in Settings, in which case it stays offline until reconnected manually. |
| Owner commands say unauthorized | `OWNER_ID` in `.env` doesn't match your numeric Telegram ID — verify with @userinfobot. An added admin seeing this on `/settings` specifically is expected — Settings is owner-only. |
| Bots don't reconnect after restart | Confirm MongoDB is reachable at startup, the bot's `enabled` field is `true`, and Settings → Bot Management → **Auto Start Bots** is ON. |
| Daily stats digest never arrives | Settings → Notifications → **Daily Statistics** must be ON — it's OFF by default. It only sends once every 24h even after enabling. |
| Settings → Database shows a connection error | `MONGO_URI` is wrong, the IP isn't allow-listed on Atlas, or the cluster is paused. |
| `ImportError` about `pymongo` or `ButtonStyle` after a fresh `pip install` | A dependency version drifted past what this codebase expects — pin the versions exactly as listed in `requirements.txt` rather than upgrading them individually. |
