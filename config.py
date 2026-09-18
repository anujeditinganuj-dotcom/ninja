import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "33029767"))
API_HASH = os.environ.get("API_HASH", "5d897bed11bc8b062a12f6c1c3c5360a")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8756360185:AAGW1mGND__G40jV1dxZNSNwb8k89fMOWoI")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Anujedit:Anujedit@cluster0.7cs2nhd.mongodb.net/?appName=Cluster0")
OWNER_ID = int(os.environ.get("OWNER_ID", "8931907813"))

DATABASE_NAME = os.environ.get("DATABASE_NAME", "botcontrol")
PORT = int(os.environ.get("PORT", "8080"))
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "km9Q19FzoqTQjaVnCziEvGPkcLuZJK__FE3uiLb4x84=")
MAINTENANCE_REMINDER_HOURS = float(os.environ.get("MAINTENANCE_REMINDER_HOURS", "24"))

# Optional: channel id (e.g. -100xxxxxxxxxx) where bot connect/disconnect,
# reconnect, and new-user events across every managed bot are posted. The
# master bot must be an admin of this channel. Leave unset/empty to disable.
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "-1003925649805")) or None
