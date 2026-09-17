import csv
import io
import os
import tempfile

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from config import OWNER_ID
from database import db

UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_export:(-?\d+)$"))
    async def export_users(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)

        users = await db.bot_users.find({"bot_id": bot_id}).to_list(length=200000)
        if not users:
            return await cq.answer("No users to export yet.", show_alert=True)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["user_id", "first_seen", "last_seen", "start_count"])
        for u in users:
            writer.writerow([u["user_id"], u.get("first_seen", ""), u.get("last_seen", ""), u.get("start_count", 0)])

        path = os.path.join(tempfile.gettempdir(), f"{bot_doc['username']}_users.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(buf.getvalue())

        try:
            await cq.message.reply_document(
                path, caption=f"📥 Users export for @{bot_doc['username']} ({len(users)} users)"
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        await cq.answer()
