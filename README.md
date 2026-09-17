# BotControl Manager

A production-ready Telegram bot management system. One **Master Control Bot**
lets an owner connect and independently manage **multiple** Telegram bots —
each with its own start message, welcome photo, inline buttons, and
maintenance mode.

## Features

- Connect unlimited Telegram bots through one Master Control Bot
- Per-bot custom **Normal** and **Maintenance** start messages (text, Markdown/HTML, emoji)
- Per-bot **welcome photo** support, stored by Telegram `file_id` (no local downloads)
- Per-bot inline buttons (multi-row)
- Per-bot maintenance mode toggle — switches the `/start` response instantly
- `/mybots`-style bot list, live preview, and per-bot statistics (users, starts, connected date)
- **Broadcast** — message every user of a specific bot, with FloodWait-safe rate limiting
- **Force-Subscribe** — require users to join a channel before a bot's `/start` message is shown
- **Export Users** — download a bot's user list as CSV
- **Backup & Restore** — export all bot configs to JSON and restore them with `/restore`
- **Combined statistics** — total users/starts across every connected bot, not just per-bot
- Owner-only access (`OWNER_ID`); everyone else is rejected
- Bot tokens encrypted at rest (Fernet), masked in the UI, never logged
- Each managed bot runs as an independent async client — one bot crashing or
  being disconnected never affects the Master Bot or any other managed bot
- Automatic startup recovery: all enabled bots reconnect from MongoDB after a restart
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
```

Generate an encryption key so bot tokens are stored encrypted:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

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

## How to connect a managed bot

1. Open the Master Bot, send `/start`.
2. Tap **➕ Connect Bot**.
3. Send the bot token from @BotFather.
4. Review the detected name/username/ID, tap **✅ Confirm**.
5. The bot is saved to MongoDB and started immediately.

## How to enable maintenance

1. `/mybots` → pick the bot → **🛠 Maintenance** → **🟢 Enable** / **🔴 Disable**.
2. Users who send `/start` to that bot instantly get the maintenance message
   until you disable it again.

## How to set custom messages

1. Pick the bot → **✏️ Edit Message** → choose **Normal** or **Maintenance**.
2. Send text, or a photo/video/document/animation with a caption.
3. The message is saved against that bot's ID only — other bots are untouched.

To only change the welcome image without touching the text, use
**🖼 Edit Welcome Photo** instead.

## How to add buttons

1. Pick the bot → **🔘 Buttons** → send the button label, then its URL.
2. Repeat to add more buttons (each addition starts a new row).

## Troubleshooting

| Problem | Cause / fix |
|---|---|
| `❌ Invalid bot token` | Token was mistyped, revoked, or already connected — request a fresh one from @BotFather. |
| `TelegramConflictError` | Another process is already polling the same bot token. Make sure only one instance of `main.py` (or one Docker/Render deployment) is running. |
| Bot shows offline in **My Bots** | Check `MONGO_URI` connectivity and the app logs; the watchdog auto-restarts a bot whose client stops responding. |
| Owner commands say unauthorized | `OWNER_ID` in `.env` doesn't match your numeric Telegram ID — verify with @userinfobot. |
| Bots don't reconnect after restart | Confirm MongoDB is reachable at startup and that the bot's `enabled` field is `true`. |
