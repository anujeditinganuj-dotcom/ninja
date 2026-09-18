from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from database import db
from handlers.bots import build_bot_panel_text
from keyboards.inline import bot_panel_keyboard, buttons_menu_keyboard, confirm_keyboard
from services.button_service import add_button, clear_buttons, remove_button
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state
from utils.validators import is_valid_url
from services.admin_service import is_admin
UNAUTHORIZED = "❌ You are not authorized to use this control panel."




async def _show_buttons_menu(cq_or_msg, client: Client, bot_id: int, edit: bool = True):
    bot_doc = await db.bots.find_one({"bot_id": bot_id})
    buttons = (bot_doc or {}).get("buttons", []) or []
    if buttons:
        text = "🔘 **Buttons**\n\nTap a button below to delete it, or add a new one."
    else:
        text = "🔘 **Buttons**\n\nNo buttons set yet for this bot."
    markup = buttons_menu_keyboard(bot_id, buttons)
    if edit:
        await cq_or_msg.message.edit_text(text, reply_markup=markup)
    else:
        await cq_or_msg.reply_text(text, reply_markup=markup)


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_buttons:(-?\d+)$"))
    async def buttons_menu(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await _show_buttons_menu(cq, client, bot_id)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^addbtn:(-?\d+)$"))
    async def add_button_start(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_button_name", {"bot_id": bot_id})
        await cq.message.edit_text(
            "🔘 **Add Button**\n\nSend the button name (e.g. 📢 Updates).\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^delbtn:(-?\d+):(\d+):(\d+)$"))
    async def delete_button(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id, row, col = int(cq.matches[0].group(1)), int(cq.matches[0].group(2)), int(cq.matches[0].group(3))
        await remove_button(bot_id, row, col)
        await cq.answer("Button deleted.", show_alert=True)
        await _show_buttons_menu(cq, client, bot_id)

    @app.on_callback_query(filters.regex(r"^clearbtns:(-?\d+)$"))
    async def clear_buttons_confirm(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await cq.message.edit_text(
            "⚠️ Delete **all** buttons for this bot?",
            reply_markup=confirm_keyboard(f"clearbtns_yes:{bot_id}", f"bot_buttons:{bot_id}"),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^clearbtns_yes:(-?\d+)$"))
    async def clear_buttons_do(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await clear_buttons(bot_id)
        await cq.answer("All buttons cleared.", show_alert=True)
        await _show_buttons_menu(cq, client, bot_id)

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_button_name")
    )
    async def receive_button_name(client: Client, message: Message):
        if not is_admin(message.from_user.id):
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
        if not is_admin(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id, name = state["data"]["bot_id"], state["data"]["name"]
        url = message.text.strip()
        if not is_valid_url(url):
            await message.reply_text("❌ Invalid URL. Please send a valid https:// URL, or /cancel.")
            return
        clear_state(message.from_user.id)
        await add_button(bot_id, name, url, new_row=True)
        await message.reply_text("✅ Button added.")
        await _show_buttons_menu(message, client, bot_id, edit=False)
