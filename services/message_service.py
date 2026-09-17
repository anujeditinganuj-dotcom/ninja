from database import db


async def set_message(bot_id: int, kind: str, text: str = None, media_type: str = None,
                       file_id: str = None, caption: str = None) -> None:
    """kind is 'normal' or 'maintenance'.

    Bug fix: this used to unconditionally overwrite the whole stored message,
    so if a photo had already been attached (either sent together here, or
    set separately via "Edit Welcome Photo"/set_welcome_photo), a LATER
    plain-text-only edit here reset media_type/file_id to None and silently
    wiped that photo out — the admin would see both "✅ updated" confirmations
    succeed, but end users would only ever get the bare text, never the
    photo+caption combo. Now: a plain-text update (media_type is None) keeps
    whatever media is already attached and just refreshes the text/caption
    on top of it. Sending an actual photo/video/document/animation here still
    fully replaces any previous media, since that's a deliberate media swap.
    """
    field = "normal_message" if kind == "normal" else "maintenance_message"

    if media_type is None:
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        existing = (bot_doc or {}).get(field, {}) or {}
        existing_media_type, existing_file_id = existing.get("media_type"), existing.get("file_id")
        if existing_media_type and existing_file_id:
            content = {
                "text": text,
                "media_type": existing_media_type,
                "file_id": existing_file_id,
                "caption": text,
            }
            await db.bots.update_one({"bot_id": bot_id}, {"$set": {field: content}})
            return

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
