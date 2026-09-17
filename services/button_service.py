from database import db


async def add_button(bot_id: int, text: str, url: str, new_row: bool = True) -> list:
    bot_doc = await db.bots.find_one({"bot_id": bot_id})
    buttons = (bot_doc or {}).get("buttons", []) or []
    if new_row or not buttons:
        buttons.append([{"text": text, "url": url}])
    else:
        buttons[-1].append({"text": text, "url": url})
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {"buttons": buttons}})
    return buttons


async def clear_buttons(bot_id: int) -> None:
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {"buttons": []}})
