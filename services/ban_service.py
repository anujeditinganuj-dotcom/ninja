import time

from database import db


async def ban_user(bot_id: int, user_id: int) -> None:
    await db.banned_users.update_one(
        {"bot_id": bot_id, "user_id": user_id},
        {"$set": {"bot_id": bot_id, "user_id": user_id, "banned_at": int(time.time())}},
        upsert=True,
    )


async def unban_user(bot_id: int, user_id: int) -> bool:
    """Returns True if the user was actually banned (and is now unbanned)."""
    result = await db.banned_users.delete_one({"bot_id": bot_id, "user_id": user_id})
    return result.deleted_count > 0


async def is_banned(bot_id: int, user_id: int) -> bool:
    doc = await db.banned_users.find_one({"bot_id": bot_id, "user_id": user_id})
    return doc is not None


async def list_banned(bot_id: int, limit: int = 50) -> list:
    cursor = db.banned_users.find({"bot_id": bot_id}).sort("banned_at", -1).limit(limit)
    return [doc["user_id"] async for doc in cursor]


async def count_banned(bot_id: int) -> int:
    return await db.banned_users.count_documents({"bot_id": bot_id})
