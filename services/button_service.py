from database import db


async def add_button(
    bot_id: int, text: str, url: str, new_row: bool = True,
    emoji_prefix: str = "", emoji_suffix: str = "", color: str | None = None,
) -> list:
    bot_doc = await db.bots.find_one({"bot_id": bot_id})
    buttons = (bot_doc or {}).get("buttons", []) or []
    btn = {"text": text, "url": url, "emoji_prefix": emoji_prefix, "emoji_suffix": emoji_suffix, "color": color}
    if new_row or not buttons:
        buttons.append([btn])
    else:
        buttons[-1].append(btn)
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {"buttons": buttons}})
    return buttons


async def clear_buttons(bot_id: int) -> None:
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {"buttons": []}})
