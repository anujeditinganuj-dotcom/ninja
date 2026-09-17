import json
import logging
import os
import tempfile
import time

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from keyboards.inline import dashboard_keyboard
from services.bot_manager import bot_manager
from utils.security import decrypt_token, is_encryption_enabled
from utils.state import clear_state, get_state, set_state

logger = logging.getLogger("botcontrol")
UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex("^backup_export$"))
    async def backup_export(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)

        bots = await db.bots.find().to_list(length=10000)
        for b in bots:
            b.pop("_id", None)

        path = os.path.join(tempfile.gettempdir(), f"botcontrol_backup_{int(time.time())}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"bots": bots}, f, indent=2, default=str)

        if is_encryption_enabled():
            token_note = (
                "Tokens inside are still **encrypted** — keep this file *and* your "
                "ENCRYPTION_KEY safe."
            )
        else:
            token_note = (
                "⚠️ ENCRYPTION_KEY is not set, so tokens inside this file are "
                "**plain text**. Keep it somewhere private."
            )
        try:
            await cq.message.reply_document(
                path,
                caption=f"💾 Backup complete.\n\n{token_note} Restore with /restore and attach this file.",
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        await cq.answer()

    @app.on_message(filters.private & filters.command("restore"))
    async def restore_cmd(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return await message.reply_text(UNAUTHORIZED)
        set_state(message.from_user.id, "awaiting_restore_file")
        await message.reply_text("📤 Send the backup JSON file to restore, or /cancel to abort.")

    @app.on_message(
        filters.private
        & filters.document
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_restore_file")
    )
    async def restore_receive(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        clear_state(message.from_user.id)

        path = await message.download()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            await message.reply_text(f"❌ Could not read backup file: {e}")
            return
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        bots = data.get("bots", [])
        if not bots:
            await message.reply_text("❌ Backup file has no bots to restore.")
            return

        restored = started = 0
        for b in bots:
            bot_id = b.get("bot_id")
            token = b.get("token")
            if not bot_id or not token:
                continue
            await db.bots.update_one({"bot_id": bot_id}, {"$set": b}, upsert=True)
            restored += 1
            should_be_live = b.get("maintenance_mode") or b.get("go_live")
            if b.get("enabled") and should_be_live and not bot_manager.is_running(bot_id):
                runtime_doc = dict(b)
                runtime_doc["token"] = decrypt_token(token)
                ok, msg = await bot_manager.start_bot(runtime_doc)
                if ok:
                    started += 1
                else:
                    logger.warning(f"Restore: failed to start bot {bot_id}: {msg}")

        await message.reply_text(
            f"✅ Restore complete.\n\nRestored: {restored} bots\nStarted: {started} bots",
            reply_markup=dashboard_keyboard(),
        )
