import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "33029767"))
API_HASH = os.environ.get("API_HASH", "5d897bed11bc8b062a12f6c1c3c5360a")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8986691330:AAHqk29Id7Rxz_7ErbJeli4uhnOMPrUcH0g")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Anujedit:Anujedit@cluster0.7cs2nhd.mongodb.net/?appName=Cluster0")
OWNER_ID = int(os.environ.get("OWNER_ID", "8931907813"))

DATABASE_NAME = os.environ.get("DATABASE_NAME", "botcontrol")
PORT = int(os.environ.get("PORT", "8080"))
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "e7109544dab612bd5b80b8a427ac474ba5541b9efff7a4ca1c8ef85df2489c23")
MAINTENANCE_REMINDER_HOURS = float(os.environ.get("MAINTENANCE_REMINDER_HOURS", "24"))
