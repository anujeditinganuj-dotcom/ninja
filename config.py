import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority")
OWNER_ID = int(os.environ.get("OWNER_ID", "123456789"))

DATABASE_NAME = os.environ.get("DATABASE_NAME", "botcontrol")
PORT = int(os.environ.get("PORT", "8080"))
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")
MAINTENANCE_REMINDER_HOURS = float(os.environ.get("MAINTENANCE_REMINDER_HOURS", "6"))
