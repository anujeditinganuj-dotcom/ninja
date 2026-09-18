import time

from database import db


async def record_start(bot_id: int, user_id: int) -> bool:
    """Returns True if this user_id is starting this bot for the first time."""
    now = int(time.time())
    existing = await db.bot_users.find_one({"bot_id": bot_id, "user_id": user_id})
    if existing:
        await db.bot_users.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {"$set": {"last_seen": now}, "$inc": {"start_count": 1}},
        )
        is_new = False
    else:
        await db.bot_users.insert_one({
            "bot_id": bot_id,
            "user_id": user_id,
            "first_seen": now,
            "last_seen": now,
            "start_count": 1,
        })
        is_new = True
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {"last_activity": now}})
    return is_new


async def record_seen(bot_id: int, user_id: int) -> None:
    """Like record_start, but for non-/start messages: tracks the user and
    activity timestamp without inflating start_count."""
    now = int(time.time())
    existing = await db.bot_users.find_one({"bot_id": bot_id, "user_id": user_id})
    if existing:
        await db.bot_users.update_one(
            {"bot_id": bot_id, "user_id": user_id},
            {"$set": {"last_seen": now}},
        )
    else:
        await db.bot_users.insert_one({
            "bot_id": bot_id,
            "user_id": user_id,
            "first_seen": now,
            "last_seen": now,
            "start_count": 0,
        })
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {"last_activity": now}})


async def get_stats(bot_id: int) -> dict:
    total_users = await db.bot_users.count_documents({"bot_id": bot_id})
    pipeline = [
        {"$match": {"bot_id": bot_id}},
        {"$group": {"_id": None, "total": {"$sum": "$start_count"}}},
    ]
    result = await db.bot_users.aggregate(pipeline).to_list(length=1)
    total_starts = result[0]["total"] if result else 0
    return {"total_users": total_users, "total_starts": total_starts}
