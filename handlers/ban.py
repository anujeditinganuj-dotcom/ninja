from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from database import db
from keyboards.inline import back_keyboard, ban_menu_keyboard, bot_picker_keyboard
from services import ban_service
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state
from services.admin_service import is_admin
UNAUTHORIZED = "❌ You are not authorized to use this control panel."




def _extract_user_id(message: Message) -> int | None:
    """Accepts either a forwarded message from the target user, or a plain
    numeric user ID typed directly."""
    if message.forward_from:
        return message.forward_from.id
    text = (message.text or "").strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def register(app: Client) -> None:
    @app.on_message(filters.private & filters.command(["ban", "unban"]))
    async def ban_unban_cmd(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply_text(UNAUTHORIZED)
        clear_state(message.from_user.id)
        cmd = message.command[0].lower()
        bots = await db.bots.find().to_list(length=500)
        if not bots:
            return await message.reply_text("🤖 No bots connected yet. Use /connect first.")
        if cmd == "ban":
            text, prefix = "🚫 **Ban User**\n\nSelect which bot:", "bot_ban_start"
        else:
            text, prefix = "✅ **Unban User**\n\nSelect which bot:", "bot_unban_start"
        await message.reply_text(text, reply_markup=bot_picker_keyboard(bots, prefix))

    @app.on_callback_query(filters.regex(r"^bot_ban_menu:(-?\d+)$"))
    async def ban_menu_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        count = await ban_service.count_banned(bot_id)
        await cq.message.edit_text(
            f"🚫 Ban / Unban — @{bot_doc['username']}\n\n"
            f"Currently banned: {count}\n\n"
            "Banned users get no reply at all from this bot — /start, "
            "buttons, everything is silently ignored.",
            reply_markup=ban_menu_keyboard(bot_id),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_ban_start:(-?\d+)$"))
    async def ban_start_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_ban_user_id", {"bot_id": bot_id})
        await cq.message.edit_text(
            "🚫 Ban User\n\n"
            "Forward a message from the user, or send their numeric "
            "Telegram user ID.\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_unban_start:(-?\d+)$"))
    async def unban_start_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_unban_user_id", {"bot_id": bot_id})
        await cq.message.edit_text(
            "✅ Unban User\n\n"
            "Forward a message from the user, or send their numeric "
            "Telegram user ID.\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_ban_list:(-?\d+)$"))
    async def ban_list_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        user_ids = await ban_service.list_banned(bot_id)
        if not user_ids:
            text = "📋 Banned List\n\nNo banned users."
        else:
            lines = "\n".join(f"{i + 1}. `{uid}`" for i, uid in enumerate(user_ids))
            text = f"📋 Banned List ({len(user_ids)})\n\n{lines}"
        await cq.message.edit_text(text, reply_markup=back_keyboard(f"bot_ban_menu:{bot_id}"))
        await cq.answer()

    @app.on_message(
        filters.private
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_ban_user_id")
    )
    async def receive_ban_target(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id = state["data"]["bot_id"]
        user_id = _extract_user_id(message)
        if user_id is None:
            await message.reply_text(
                "❌ Couldn't read a user ID from that. Forward a message from "
                "the user, or send their numeric ID, or /cancel."
            )
            return
        clear_state(message.from_user.id)
        await ban_service.ban_user(bot_id, user_id)
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        uname = bot_doc["username"] if bot_doc else bot_id
        await message.reply_text(
            f"🚫 User `{user_id}` banned from @{uname}.",
            reply_markup=ban_menu_keyboard(bot_id),
        )

    @app.on_message(
        filters.private
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_unban_user_id")
    )
    async def receive_unban_target(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id = state["data"]["bot_id"]
        user_id = _extract_user_id(message)
        if user_id is None:
            await message.reply_text(
                "❌ Couldn't read a user ID from that. Forward a message from "
                "the user, or send their numeric ID, or /cancel."
            )
            return
        clear_state(message.from_user.id)
        was_banned = await ban_service.unban_user(bot_id, user_id)
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        uname = bot_doc["username"] if bot_doc else bot_id
        if was_banned:
            text = f"✅ User `{user_id}` unbanned from @{uname}."
        else:
            text = f"ℹ️ User `{user_id}` wasn't banned on @{uname}."
        await message.reply_text(text, reply_markup=ban_menu_keyboard(bot_id))
