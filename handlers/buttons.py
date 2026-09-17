from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from handlers.bots import build_bot_panel_text
from keyboards.inline import bot_panel_keyboard
from services.button_service import add_button
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state
from utils.validators import is_valid_url

UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_buttons:(-?\d+)$"))
    async def buttons_menu(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_button_name", {"bot_id": bot_id})
        await cq.message.edit_text(
            "🔘 **Set Buttons**\n\nSend the button name (e.g. 📢 Updates).\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_button_name")
    )
    async def receive_button_name(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id = state["data"]["bot_id"]
        set_state(message.from_user.id, "awaiting_button_url", {"bot_id": bot_id, "name": message.text.strip()})
        await message.reply_text("Now send the button URL:")

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_button_url")
    )
    async def receive_button_url(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id, name = state["data"]["bot_id"], state["data"]["name"]
        url = message.text.strip()
        if not is_valid_url(url):
            await message.reply_text("❌ Invalid URL. Please send a valid https:// URL, or /cancel.")
            return
        clear_state(message.from_user.id)
        await add_button(bot_id, name, url, new_row=True)
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        text = await build_bot_panel_text(bot_doc)
        await message.reply_text(f"✅ Button added.\n\n{text}", reply_markup=bot_panel_keyboard(bot_id))
