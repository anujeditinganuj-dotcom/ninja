from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from handlers.bots import build_bot_panel_text
from keyboards.inline import (
    BUTTON_EMOJI_PRESETS,
    bot_panel_keyboard,
    button_color_keyboard,
    button_emoji_keyboard,
)
from services.button_service import add_button
from utils.state import clear_state, get_state, set_state
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
        set_state(message.from_user.id, "awaiting_button_emoji", {"bot_id": bot_id, "name": name, "url": url})
        await message.reply_text(
            "🎨 Pick an emoji style for this button (wraps the text like "
            f"{BUTTON_EMOJI_PRESETS['heart'][0]}{name}{BUTTON_EMOJI_PRESETS['heart'][1]}):",
            reply_markup=button_emoji_keyboard(),
        )

    @app.on_callback_query(filters.regex(r"^btnemoji:(\w+)$"))
    async def pick_emoji(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state = get_state(cq.from_user.id)
        if not state or state.get("action") != "awaiting_button_emoji":
            return await cq.answer("This selection has expired — start again from 🔘 Buttons.", show_alert=True)
        key = cq.matches[0].group(1)
        preset = BUTTON_EMOJI_PRESETS.get(key, BUTTON_EMOJI_PRESETS["none"])
        prefix, suffix, _ = preset
        data = dict(state["data"])
        data["emoji_prefix"], data["emoji_suffix"] = prefix, suffix
        set_state(cq.from_user.id, "awaiting_button_color", data)
        preview = f"{prefix}{data['name']}{suffix}"
        await cq.message.edit_text(
            f"🎨 Now pick a color for: {preview}",
            reply_markup=button_color_keyboard(),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^btncolor:(\w+)$"))
    async def pick_color(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state = get_state(cq.from_user.id)
        if not state or state.get("action") != "awaiting_button_color":
            return await cq.answer("This selection has expired — start again from 🔘 Buttons.", show_alert=True)
        color = cq.matches[0].group(1)
        data = state["data"]
        clear_state(cq.from_user.id)
        await add_button(
            data["bot_id"], data["name"], data["url"], new_row=True,
            emoji_prefix=data.get("emoji_prefix", ""), emoji_suffix=data.get("emoji_suffix", ""),
            color=None if color == "default" else color,
        )
        bot_doc = await db.bots.find_one({"bot_id": data["bot_id"]})
        text = await build_bot_panel_text(bot_doc)
        await cq.answer("✅ Button added.")
        await cq.message.edit_text(text, reply_markup=bot_panel_keyboard(data["bot_id"]))

    @app.on_callback_query(filters.regex("^btnstyle_cancel$"))
    async def style_cancel(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state = get_state(cq.from_user.id)
        bot_id = (state or {}).get("data", {}).get("bot_id")
        clear_state(cq.from_user.id)
        await cq.answer("Cancelled — button not added.")
        if bot_id:
            bot_doc = await db.bots.find_one({"bot_id": bot_id})
            text = await build_bot_panel_text(bot_doc)
            await cq.message.edit_text(text, reply_markup=bot_panel_keyboard(bot_id))
