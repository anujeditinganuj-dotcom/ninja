import asyncio
import logging
import os

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from database import db
from keyboards.inline import bot_panel_keyboard, bot_picker_keyboard, confirm_keyboard
from services import telegram_api
from utils.security import decrypt_token
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state
from services.admin_service import is_admin
UNAUTHORIZED = "❌ You are not authorized to use this control panel."


logger = logging.getLogger("botcontrol")
SEND_DELAY = 0.05  # ~20 messages/sec, safely under Telegram's bot API limits



async def _prepare_broadcast_content(client: Client, token: str, owner_id: int, message: Message) -> dict:
    """Builds the {"type", "text"/"file_id", "caption"} broadcast payload.
    For media, the file_id the admin's message carries was minted by the
    MASTER bot's session and is not valid for a different bot — it's
    downloaded here (via the master client, a plain MTProto download, not a
    poller) and re-uploaded once through the target bot's own HTTP API to
    mint a file_id that bot can actually use for every subsequent send.
    """
    if message.photo:
        media_type, src_file_id, caption = "photo", message.photo.file_id, message.caption
    elif message.video:
        media_type, src_file_id, caption = "video", message.video.file_id, message.caption
    elif message.document:
        media_type, src_file_id, caption = "document", message.document.file_id, message.caption
    elif message.animation:
        media_type, src_file_id, caption = "animation", message.animation.file_id, message.caption
    else:
        return {"type": "text", "text": message.text or ""}

    path = None
    try:
        path = await client.download_media(src_file_id)
        new_file_id = await telegram_api.upload_media_for_file_id(token, owner_id, media_type, path)
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    if not new_file_id:
        return {"type": "error"}

    return {"type": media_type, "file_id": new_file_id, "caption": caption}


def register(app: Client) -> None:
    # Bug fix: /broadcast was already advertised in main.py's Telegram
    # command menu, and there's a "📢 Broadcast" button on the dashboard
    # now too — but until now, broadcasting was reachable ONLY through a
    # specific bot's own panel (My Bots → pick a bot → Broadcast). Tapping
    # /broadcast, or the dashboard button, did nothing at all. Both now show
    # the same bot-picker used by /ban and /unban; picking a bot from it
    # reuses the existing bot_broadcast:{bot_id} callback below unchanged.
    async def _show_broadcast_bot_picker(client: Client, chat_id: int) -> None:
        bots = await db.bots.find().to_list(length=500)
        if not bots:
            await client.send_message(chat_id, "🤖 No bots connected yet. Use /connect first.")
            return
        await client.send_message(
            chat_id, "📢 **Broadcast**\n\nSelect which bot:",
            reply_markup=bot_picker_keyboard(bots, "bot_broadcast"),
        )

    @app.on_message(filters.private & filters.command("broadcast"))
    async def broadcast_cmd(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply_text(UNAUTHORIZED)
        clear_state(message.from_user.id)
        await _show_broadcast_bot_picker(client, message.chat.id)

    @app.on_callback_query(filters.regex("^broadcast_menu$"))
    async def broadcast_menu_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        clear_state(cq.from_user.id)
        try:
            await cq.message.delete()
        except Exception:
            pass
        await _show_broadcast_bot_picker(client, cq.message.chat.id)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_broadcast:(-?\d+)$"))
    async def broadcast_start(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_broadcast", {"bot_id": bot_id})
        await cq.message.edit_text(
            "📢 **Broadcast**\n\nSend the message (text, or a photo/video/document/animation with a "
            "caption) to broadcast to every user who has started this bot.\n\n"
            "This works even if the bot is currently hosted elsewhere — broadcasting only "
            "*sends* messages, it never needs to be the one receiving this bot's updates.\n\n"
            "Send /cancel to abort."
        )
        await cq.answer()

    @app.on_message(
        filters.private
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_broadcast")
    )
    async def broadcast_receive(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id = state["data"]["bot_id"]
        clear_state(message.from_user.id)

        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await message.reply_text("Bot not found.")
        token = decrypt_token(bot_doc["token"])

        status_msg = await message.reply_text("Preparing broadcast content…")
        content = await _prepare_broadcast_content(client, token, message.from_user.id, message)
        if content["type"] == "error":
            return await status_msg.edit_text(
                "❌ Could not prepare that media for this bot (upload failed). Try again, or use plain text."
            )

        set_state(message.from_user.id, "confirm_broadcast", {"bot_id": bot_id, "content": content})
        count = await db.bot_users.count_documents({"bot_id": bot_id})
        await status_msg.edit_text(
            f"This will be sent to **{count}** users of @{bot_doc['username']}. Continue?",
        )
        await message.reply_text(
            "Confirm broadcast?",
            reply_markup=confirm_keyboard("broadcast_confirm_yes", "broadcast_confirm_no"),
        )

    @app.on_callback_query(filters.regex("^broadcast_confirm_no$"))
    async def broadcast_cancel(client: Client, cq: CallbackQuery):
        clear_state(cq.from_user.id)
        await cq.message.edit_text("Broadcast cancelled.")
        await cq.answer()

    @app.on_callback_query(filters.regex("^broadcast_confirm_yes$"))
    async def broadcast_confirm(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state = get_state(cq.from_user.id)
        if not state or state["action"] != "confirm_broadcast":
            return await cq.answer("Session expired, please try again.", show_alert=True)
        bot_id, content = state["data"]["bot_id"], state["data"]["content"]
        clear_state(cq.from_user.id)

        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        token = decrypt_token(bot_doc["token"])

        await cq.answer("Broadcast started.", show_alert=True)
        await cq.message.edit_text("📢 Broadcasting... this may take a while for large user lists.")

        stored_content = (
            {"text": content["text"]} if content["type"] == "text"
            else {"media_type": content["type"], "file_id": content["file_id"], "caption": content.get("caption")}
        )

        sent = failed = 0
        cursor = db.bot_users.find({"bot_id": bot_id}, {"user_id": 1})
        async for doc in cursor:
            uid = doc["user_id"]
            ok, data = await telegram_api.send_content(token, uid, stored_content)
            if ok:
                sent += 1
            elif data.get("error_code") == 429:
                retry_after = int(data.get("parameters", {}).get("retry_after", 1))
                await asyncio.sleep(retry_after)
                ok2, _ = await telegram_api.send_content(token, uid, stored_content)
                sent += 1 if ok2 else 0
                failed += 0 if ok2 else 1
            else:
                failed += 1
            await asyncio.sleep(SEND_DELAY)

        await cq.message.reply_text(
            f"✅ Broadcast finished for @{bot_doc['username']}.\n\nSent: {sent}\nFailed: {failed}",
            reply_markup=bot_panel_keyboard(bot_id),
        )
