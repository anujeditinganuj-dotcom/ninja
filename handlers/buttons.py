from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from keyboards.inline import (
    BUTTON_EMOJI_PRESETS,
    button_color_keyboard,
    button_emoji_keyboard,
    button_recolor_keyboard,
    buttons_manage_keyboard,
    confirm_keyboard,
)
from services.button_service import add_button, clear_buttons, remove_button, set_button_color
from utils.state import clear_state, get_state, set_state
from utils.validators import is_valid_url

UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app: Client) -> None:
    async def _show_manage_menu(cq: CallbackQuery, bot_id: int) -> None:
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        buttons = (bot_doc or {}).get("buttons", []) or []
        count = sum(len(row) for row in buttons)
        await cq.message.edit_text(
            f"🔘 **Manage Buttons**\n\nCurrently set: {count}\n\nTap a button below to delete it.",
            reply_markup=buttons_manage_keyboard(bot_id, buttons),
        )

    @app.on_callback_query(filters.regex(r"^bot_buttons:(-?\d+)$"))
    async def buttons_menu(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await _show_manage_menu(cq, bot_id)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_buttons_add:(-?\d+)$"))
    async def buttons_add_start(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_button_name", {"bot_id": bot_id})
        await cq.message.edit_text(
            "🔘 **Add Button**\n\nSend the button name (e.g. 📢 Updates).\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^noop$"))
    async def noop_cb(client: Client, cq: CallbackQuery):
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^btn_remove:(-?\d+):(\d+):(\d+)$"))
    async def btn_remove_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id, row, col = int(cq.matches[0].group(1)), int(cq.matches[0].group(2)), int(cq.matches[0].group(3))
        await remove_button(bot_id, row, col)
        await cq.answer("🗑 Removed.")
        await _show_manage_menu(cq, bot_id)

    @app.on_callback_query(filters.regex(r"^btn_recolor:(-?\d+):(\d+):(\d+)$"))
    async def btn_recolor_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id, row, col = int(cq.matches[0].group(1)), int(cq.matches[0].group(2)), int(cq.matches[0].group(3))
        await cq.message.edit_text(
            "🎨 Pick a new color for this button:",
            reply_markup=button_recolor_keyboard(bot_id, row, col),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^btn_setcolor:(-?\d+):(\d+):(\d+):(\w+)$"))
    async def btn_setcolor_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id, row, col, key = (int(cq.matches[0].group(1)), int(cq.matches[0].group(2)),
                                  int(cq.matches[0].group(3)), cq.matches[0].group(4))
        await set_button_color(bot_id, row, col, None if key == "default" else key)
        await cq.answer("✅ Color updated.")
        await _show_manage_menu(cq, bot_id)

    @app.on_callback_query(filters.regex(r"^bot_buttons_clear:(-?\d+)$"))
    async def buttons_clear_confirm(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await cq.message.edit_text(
            "⚠️ Remove **all** buttons from this bot?",
            reply_markup=confirm_keyboard(f"bot_buttons_clear_yes:{bot_id}", f"bot_buttons:{bot_id}"),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_buttons_clear_yes:(-?\d+)$"))
    async def buttons_clear_yes(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await clear_buttons(bot_id)
        await cq.answer("🧹 All buttons cleared.")
        await _show_manage_menu(cq, bot_id)

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
        await cq.answer("✅ Button added.")
        await _show_manage_menu(cq, data["bot_id"])

    @app.on_callback_query(filters.regex("^btnstyle_cancel$"))
    async def style_cancel(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state = get_state(cq.from_user.id)
        bot_id = (state or {}).get("data", {}).get("bot_id")
        clear_state(cq.from_user.id)
        await cq.answer("Cancelled — button not added.")
        if bot_id:
            await _show_manage_menu(cq, bot_id)
