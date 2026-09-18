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


async def remove_button(bot_id: int, row: int, col: int) -> list:
    """Removes one button by its [row][col] position (as shown in the manage
    menu). Drops the whole row if it becomes empty, so no blank rows are
    ever left behind in the keyboard."""
    bot_doc = await db.bots.find_one({"bot_id": bot_id})
    buttons = (bot_doc or {}).get("buttons", []) or []
    if 0 <= row < len(buttons) and 0 <= col < len(buttons[row]):
        buttons[row].pop(col)
        if not buttons[row]:
            buttons.pop(row)
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {"buttons": buttons}})
    return buttons


async def set_button_color(bot_id: int, row: int, col: int, color: str | None) -> list:
    """Recolors one existing button in place (by [row][col] position)
    without touching its text/url/emoji — for buttons that were created
    before a color was ever picked, or to just change it later."""
    bot_doc = await db.bots.find_one({"bot_id": bot_id})
    buttons = (bot_doc or {}).get("buttons", []) or []
    if 0 <= row < len(buttons) and 0 <= col < len(buttons[row]):
        buttons[row][col]["color"] = color
        await db.bots.update_one({"bot_id": bot_id}, {"$set": {"buttons": buttons}})
    return buttons
