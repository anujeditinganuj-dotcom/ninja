import datetime

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from config import OWNER_ID
from database import db
from keyboards.inline import bot_panel_keyboard, dashboard_keyboard
from services.bot_manager import bot_manager
from services.statistics import get_stats

UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def show_overview_stats(client: Client, chat_id: int) -> None:
    bots = await db.bots.find().to_list(length=1000)
    total_bots = len(bots)
    online = sum(1 for b in bots if bot_manager.is_running(b["bot_id"]))
    maint = sum(1 for b in bots if b.get("maintenance_mode"))

    total_users = await db.bot_users.count_documents({})
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$start_count"}}}]
    result = await db.bot_users.aggregate(pipeline).to_list(length=1)
    total_starts = result[0]["total"] if result else 0

    await client.send_message(
        chat_id,
        f"📊 **Overview Statistics**\n\n"
        f"🤖 Total Bots: {total_bots}\n"
        f"🟢 Online: {online}\n"
        f"🛠 Maintenance: {maint}\n\n"
        f"👥 Combined Users: {total_users}\n"
        f"🚀 Combined Starts: {total_starts}",
        reply_markup=dashboard_keyboard(),
    )


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex("^stats_menu$"))
    async def stats_menu_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await show_overview_stats(client, cq.message.chat.id)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_stats:(-?\d+)$"))
    async def bot_stats_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        stats = await get_stats(bot_id)
        connected = datetime.datetime.fromtimestamp(
            bot_doc.get("created_at", 0), tz=datetime.timezone.utc
        ).strftime("%d %b %Y")
        online = bot_manager.is_running(bot_id)
        maint = "ON" if bot_doc.get("maintenance_mode") else "OFF"
        await cq.message.edit_text(
            f"📊 @{bot_doc['username']} Statistics\n\n"
            f"👥 Users: {stats['total_users']}\n"
            f"🚀 Starts: {stats['total_starts']}\n"
            f"📅 Connected: {connected}\n"
            f"{'🟢' if online else '🔴'} Status: {'Active' if online else 'Offline'}\n"
            f"🛠 Maintenance: {maint}",
            reply_markup=bot_panel_keyboard(bot_id),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_settings:(-?\d+)$"))
    async def bot_settings_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        await cq.message.edit_text(
            f"⚙️ **Bot Settings** — @{bot_doc['username']}\n\n"
            "Use the buttons below to edit:\n"
            "• Normal Start Message\n• Welcome Photo\n• Maintenance Message\n"
            "• Maintenance Mode\n• Buttons\n• Statistics",
            reply_markup=bot_panel_keyboard(bot_id),
        )
        await cq.answer()
