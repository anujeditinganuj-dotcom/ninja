import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from keyboards.inline import bot_panel_keyboard, bot_picker_keyboard, confirm_keyboard
from services.bot_manager import bot_manager
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state

logger = logging.getLogger("botcontrol")
UNAUTHORIZED = "❌ You are not authorized to use this control panel."
SEND_DELAY = 0.05  # ~20 messages/sec, safely under Telegram's bot API limits


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def _send_one(client: Client, uid: int, content: dict) -> None:
    t = content["type"]
    if t == "text":
        await client.send_message(uid, content["text"])
    elif t == "photo":
        await client.send_photo(uid, content["file_id"], caption=content.get("caption"))
    elif t == "video":
        await client.send_video(uid, content["file_id"], caption=content.get("caption"))
    elif t == "document":
        await client.send_document(uid, content["file_id"], caption=content.get("caption"))
    elif t == "animation":
        await client.send_animation(uid, content["file_id"], caption=content.get("caption"))


def register(app: Client) -> None:
    @app.on_message(filters.private & filters.command("broadcast"))
    async def broadcast_cmd(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return await message.reply_text(UNAUTHORIZED)
        clear_state(message.from_user.id)
        bots = await db.bots.find().to_list(length=500)
        if not bots:
            return await message.reply_text("🤖 No bots connected yet. Use /connect first.")
        await message.reply_text(
            "📢 **Broadcast**\n\nSelect which bot to broadcast to:",
            reply_markup=bot_picker_keyboard(bots, "bot_broadcast"),
        )

    @app.on_callback_query(filters.regex(r"^bot_broadcast:(-?\d+)$"))
    async def broadcast_start(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_broadcast", {"bot_id": bot_id})
        await cq.message.edit_text(
            "📢 **Broadcast**\n\nSend the message (text, or a photo/video/document/animation with a "
            "caption) to broadcast to every user who has started this bot.\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_message(
        filters.private
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_broadcast")
    )
    async def broadcast_receive(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id = state["data"]["bot_id"]

        if message.photo:
            content = {"type": "photo", "file_id": message.photo.file_id, "caption": message.caption}
        elif message.video:
            content = {"type": "video", "file_id": message.video.file_id, "caption": message.caption}
        elif message.document:
            content = {"type": "document", "file_id": message.document.file_id, "caption": message.caption}
        elif message.animation:
            content = {"type": "animation", "file_id": message.animation.file_id, "caption": message.caption}
        else:
            content = {"type": "text", "text": message.text or ""}

        set_state(message.from_user.id, "confirm_broadcast", {"bot_id": bot_id, "content": content})
        count = await db.bot_users.count_documents({"bot_id": bot_id})
        await message.reply_text(
            f"This will be sent to **{count}** users of this bot. Continue?",
            reply_markup=confirm_keyboard("broadcast_confirm_yes", "broadcast_confirm_no"),
        )

    @app.on_callback_query(filters.regex("^broadcast_confirm_no$"))
    async def broadcast_cancel(client: Client, cq: CallbackQuery):
        clear_state(cq.from_user.id)
        await cq.message.edit_text("Broadcast cancelled.")
        await cq.answer()

    @app.on_callback_query(filters.regex("^broadcast_confirm_yes$"))
    async def broadcast_confirm(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state = get_state(cq.from_user.id)
        if not state or state["action"] != "confirm_broadcast":
            return await cq.answer("Session expired, please try again.", show_alert=True)
        bot_id, content = state["data"]["bot_id"], state["data"]["content"]
        clear_state(cq.from_user.id)

        managed_client = bot_manager.clients.get(bot_id)
        if not managed_client:
            return await cq.answer("This bot is not currently running.", show_alert=True)

        await cq.answer("Broadcast started.", show_alert=True)
        await cq.message.edit_text("📢 Broadcasting... this may take a while for large user lists.")

        sent = failed = 0
        cursor = db.bot_users.find({"bot_id": bot_id}, {"user_id": 1})
        async for doc in cursor:
            uid = doc["user_id"]
            try:
                await _send_one(managed_client, uid, content)
                sent += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await _send_one(managed_client, uid, content)
                    sent += 1
                except Exception:
                    failed += 1
            except Exception:
                failed += 1
            await asyncio.sleep(SEND_DELAY)

        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        await cq.message.reply_text(
            f"✅ Broadcast finished for @{bot_doc['username']}.\n\nSent: {sent}\nFailed: {failed}",
            reply_markup=bot_panel_keyboard(bot_id),
        )
