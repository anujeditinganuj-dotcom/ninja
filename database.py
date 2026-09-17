import motor.motor_asyncio

from config import MONGO_URI, DATABASE_NAME

_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = _client[DATABASE_NAME]


async def init_indexes():
    """Create required MongoDB indexes. Safe to call on every startup."""
    await db.bots.create_index("bot_id", unique=True)
    await db.bots.create_index("token_id", unique=True)
    await db.bot_users.create_index([("bot_id", 1), ("user_id", 1)], unique=True)
    await db.admins.create_index("user_id", unique=True)
    await db.banned_users.create_index([("bot_id", 1), ("user_id", 1)], unique=True)
