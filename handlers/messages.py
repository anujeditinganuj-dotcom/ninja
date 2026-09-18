from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from keyboards.inline import bot_panel_keyboard, message_type_keyboard
from services.bot_manager import bot_manager
from services.message_service import set_message, set_welcome_photo
from utils.logging import get_logger
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state

logger = get_logger(__name__)

NOT_CONNECTED = (
    "⚠️ This bot isn't connected right now, so the {kind} couldn't be cached for it "
    "(a file sent to this panel only works for the bot that's live and running).\n\n"
    "Reconnect it, then resend the {kind}."
)

UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_message:(-?\d+)$"))
    async def bot_message_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await cq.message.edit_text("✏️ **Edit Message**\n\nChoose which message to edit:",
                                    reply_markup=message_type_keyboard(bot_id))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^setmsg_(normal|maint):(-?\d+)$"))
    async def setmsg_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        kind_raw, bot_id = cq.matches[0].group(1), int(cq.matches[0].group(2))
        kind = "normal" if kind_raw == "normal" else "maintenance"
        set_state(cq.from_user.id, "awaiting_message", {"bot_id": bot_id, "kind": kind})
        await cq.message.edit_text(
            "✏️ Send the new message now.\n\n"
            "You can send plain text, or a photo/video/document/animation with a caption.\n"
            "Markdown/HTML formatting, emoji and line breaks are all supported.\n\n"
            "Send /cancel to abort."
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_photo:(-?\d+)$"))
    async def bot_photo_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_welcome_photo", {"bot_id": bot_id})
        await cq.message.edit_text(
            "🖼 **Edit Welcome Photo**\n\nSend a photo to use as the welcome image.\n\n"
            "Existing message text will be kept as the caption.\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_message(
        filters.private
        & filters.photo
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_welcome_photo")
    )
    async def receive_welcome_photo(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id = state["data"]["bot_id"]
        clear_state(message.from_user.id)

        cached_id = await bot_manager.recache_media(
            bot_id, "photo", message.photo.file_id, client, message.from_user.id
        )
        if cached_id is None:
            # recache failed — managed bot may not be connected or DM blocked.
            # Try saving the master bot's file_id directly as a best-effort
            # fallback (it may work if the bot shares the same DC as the master).
            logger.warning(
                f"recache_media failed for bot {bot_id} — "
                f"falling back to master bot file_id (may not work across DCs)"
            )
            cached_id = message.photo.file_id

        await set_welcome_photo(bot_id, cached_id)
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        await message.reply_text(
            f"✅ Welcome photo updated for @{bot_doc['username']}.",
            reply_markup=bot_panel_keyboard(bot_id),
        )

    @app.on_message(
        filters.private
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_welcome_photo")
        & ~filters.photo
        & ~filters.command(RESERVED_COMMANDS)
    )
    async def welcome_photo_wrong_type(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        await message.reply_text("Please send a photo, or /cancel to abort.")

    @app.on_message(
        filters.private
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_message")
    )
    async def receive_message_content(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id, kind = state["data"]["bot_id"], state["data"]["kind"]
        clear_state(message.from_user.id)

        text = media_type = file_id = caption = None
        if message.photo:
            media_type, file_id, caption = "photo", message.photo.file_id, message.caption
        elif message.video:
            media_type, file_id, caption = "video", message.video.file_id, message.caption
        elif message.document:
            media_type, file_id, caption = "document", message.document.file_id, message.caption
        elif message.animation:
            media_type, file_id, caption = "animation", message.animation.file_id, message.caption
        else:
            text = message.text or message.caption or ""

        if media_type:
            cached_id = await bot_manager.recache_media(bot_id, media_type, file_id, client, message.from_user.id)
            if cached_id is None:
                return await message.reply_text(NOT_CONNECTED.format(kind=media_type))
            file_id = cached_id

        await set_message(bot_id, kind, text=text, media_type=media_type, file_id=file_id, caption=caption)

        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        label = "Normal" if kind == "normal" else "Maintenance"
        await message.reply_text(
            f"✅ {label} message updated for @{bot_doc['username']}.",
            reply_markup=bot_panel_keyboard(bot_id),
        )
