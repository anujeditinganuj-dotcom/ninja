from database import db


async def set_message(bot_id: int, kind: str, text: str = None, media_type: str = None,
                       file_id: str = None, caption: str = None) -> None:
    """kind is 'normal' or 'maintenance'."""
    field = "normal_message" if kind == "normal" else "maintenance_message"
    content = {"text": text, "media_type": media_type, "file_id": file_id, "caption": caption}
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {field: content}})


async def set_welcome_photo(bot_id: int, file_id: str) -> None:
    """Updates only the media of the normal (welcome) message, keeping existing text/caption."""
    bot_doc = await db.bots.find_one({"bot_id": bot_id})
    existing = (bot_doc or {}).get("normal_message", {}) or {}
    content = {
        "text": existing.get("text"),
        "media_type": "photo",
        "file_id": file_id,
        "caption": existing.get("caption") or existing.get("text"),
    }
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {"normal_message": content}})


async def get_bot(bot_id: int):
    return await db.bots.find_one({"bot_id": bot_id})
