from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from config import OWNER_ID
from database import db
from keyboards.inline import build_user_buttons

UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_preview:(-?\d+)$"))
    async def preview_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)

        maintenance = bot_doc.get("maintenance_mode", False)
        mode = "Maintenance" if maintenance else "Normal"
        content = (bot_doc.get("maintenance_message") if maintenance else bot_doc.get("normal_message")) or {}
        markup = build_user_buttons(bot_doc.get("buttons", []))

        await cq.message.reply_text(f"👀 Preview of @{bot_doc['username']} (Mode: {mode})")

        text = content.get("text") or content.get("caption") or "Welcome!"
        media_type, file_id = content.get("media_type"), content.get("file_id")
        caption = content.get("caption") or ""
        chat_id = cq.message.chat.id
        try:
            if media_type == "photo" and file_id:
                await client.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
            elif media_type == "video" and file_id:
                await client.send_video(chat_id, file_id, caption=caption, reply_markup=markup)
            elif media_type == "document" and file_id:
                await client.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
            elif media_type == "animation" and file_id:
                await client.send_animation(chat_id, file_id, caption=caption, reply_markup=markup)
            else:
                await client.send_message(chat_id, text, reply_markup=markup)
        except Exception as e:
            await cq.message.reply_text(f"⚠️ Could not render preview: {e}")

        await cq.answer()
