from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from database import db
from services import telegram_api
from utils.security import decrypt_token
from services.admin_service import is_admin
UNAUTHORIZED = "❌ You are not authorized to use this control panel."




def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_preview:(-?\d+)$"))
    async def preview_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)

        maintenance = bot_doc.get("maintenance_mode", False)
        mode = "Maintenance" if maintenance else "Normal"
        content = (bot_doc.get("maintenance_message") if maintenance else bot_doc.get("normal_message")) or {}
        buttons = bot_doc.get("buttons", [])
        token = decrypt_token(bot_doc["token"])

        await cq.message.reply_text(f"👀 Preview of @{bot_doc['username']} (Mode: {mode})")

        # Sent via the bot's own HTTP API — works regardless of whether
        # BotControl currently has a live connection to this bot, and any
        # stored file_id is already valid for it (recached at set-time).
        ok, data = await telegram_api.send_content(token, cq.message.chat.id, content, buttons)
        if not ok:
            await cq.message.reply_text(f"⚠️ Could not render preview: {data.get('description', data)}")

        await cq.answer()
