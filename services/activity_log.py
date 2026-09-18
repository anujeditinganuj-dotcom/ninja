import time

from database import db

MAX_LOGS = 500  # keep the collection bounded — this is an audit trail, not analytics


async def log_action(user_id: int, action: str, details: str = "") -> None:
    await db.activity_logs.insert_one({
        "user_id": user_id,
        "action": action,
        "details": details,
        "ts": int(time.time()),
    })
    total = await db.activity_logs.count_documents({})
    if total > MAX_LOGS:
        overflow = total - MAX_LOGS
        old_ids = [doc["_id"] async for doc in db.activity_logs.find().sort("ts", 1).limit(overflow)]
        if old_ids:
            await db.activity_logs.delete_many({"_id": {"$in": old_ids}})


async def get_recent_logs(limit: int = 15) -> list:
    return [doc async for doc in db.activity_logs.find().sort("ts", -1).limit(limit)]
