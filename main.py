import asyncio
import logging
import time

from aiohttp import web
from pyrogram import Client
from pyrogram.types import BotCommand

from config import API_HASH, API_ID, BOT_TOKEN, MAINTENANCE_REMINDER_HOURS, OWNER_ID, PORT
from database import db, init_indexes
from handlers import admin, backup, ban, bots, broadcast, buttons, export, force_sub, maintenance, messages, preview, settings, stats
from services.bot_manager import bot_manager
from services.admin_service import load_admins
from services.settings_service import load_settings
from utils.blockquote import apply_blockquote_patch
from utils.keep_alive import keep_alive_loop
from utils.logging import setup_logging
from utils.security import decrypt_token

# Must run before any Client is created/started — wraps every outgoing
# message/caption (master bot UI + every managed bot's replies) in a
# Telegram blockquote, project-wide, from this one call.
apply_blockquote_patch()

logger = logging.getLogger("botcontrol")
REMINDER_CHECK_INTERVAL = 1800  # seconds; reminders themselves are throttled by MAINTENANCE_REMINDER_HOURS

# The BotFather-style command menu (the "/" list Telegram shows in the
# chat). Kept as one list, same as every other project-wide setting here,
# so adding a command anywhere just means adding one line below.
BOT_COMMANDS_LIST = [
    BotCommand("start", "🚀 Open the dashboard"),
    BotCommand("help", "❓ How to use BotControl Manager"),
    BotCommand("connect", "➕ Connect a new bot"),
    BotCommand("mybots", "🤖 View & manage connected bots"),
    BotCommand("stats", "📊 Combined statistics"),
    BotCommand("broadcast", "📢 Broadcast a message to a bot's users"),
    BotCommand("ban", "🚫 Ban a user from a bot"),
    BotCommand("unban", "✅ Unban a user from a bot"),
    BotCommand("settings", "⚙️ Settings"),
    BotCommand("restore", "💾 Restore bots from a backup JSON"),
    BotCommand("cancel", "🚫 Cancel the current action"),
]


async def set_bot_commands_list(client: Client) -> None:
    await client.set_bot_commands(BOT_COMMANDS_LIST)


async def health_handler(request):
    return web.json_response({"status": "online", "service": "BotControl Manager"})


async def start_health_server():
    web_app = web.Application()
    web_app.router.add_get("/", health_handler)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health endpoint listening on port {PORT}")
    return runner


async def load_and_start_bots():
    # Only reconnect bots that are meant to be live right now: either
    # Maintenance is ON (the user's own host is down and BotControl should
    # cover for it) or Go Live / Full-time hosting is ON. Everything else
    # stays disconnected by default so it never races with the user's own
    # bot host and causes a TelegramConflictError.
    cursor = db.bots.find(
        {"enabled": True, "$or": [{"maintenance_mode": True}, {"go_live": True}]}
    )
    async for bot_doc in cursor:
        runtime_doc = dict(bot_doc)
        runtime_doc["token"] = decrypt_token(bot_doc["token"])
        ok, msg = await bot_manager.start_bot(runtime_doc)
        if ok:
            logger.info(f"Reconnected managed bot @{bot_doc.get('username')}")
        else:
            logger.error(f"Failed to reconnect bot @{bot_doc.get('username')}: {msg}")
            await bot_manager.notify_owner(
                f"⚠️ **Startup reconnect failed**\n\n"
                f"@{bot_doc.get('username', bot_doc.get('bot_id'))} could not be "
                f"reconnected on boot: {msg}"
            )


async def maintenance_reminder_loop():
    """Every REMINDER_CHECK_INTERVAL, nudges the owner about bots that have
    been in Maintenance mode (BotControl standing in, not full-time) for
    longer than MAINTENANCE_REMINDER_HOURS — easy to forget to turn back off
    once the original host is back up."""
    if MAINTENANCE_REMINDER_HOURS <= 0:
        return
    threshold = MAINTENANCE_REMINDER_HOURS * 3600
    try:
        while True:
            await asyncio.sleep(REMINDER_CHECK_INTERVAL)
            now = int(time.time())
            cursor = db.bots.find({"maintenance_mode": True, "go_live": {"$ne": True}})
            async for bot_doc in cursor:
                since = bot_doc.get("maintenance_since")
                if not since:
                    continue
                last_reminder = bot_doc.get("maintenance_reminder_at") or since
                if now - last_reminder < threshold:
                    continue
                hours_on = (now - since) / 3600
                await bot_manager.notify_owner(
                    f"⏰ **Maintenance still ON**\n\n"
                    f"@{bot_doc.get('username', bot_doc.get('bot_id'))} has been "
                    f"in Maintenance mode for ~{hours_on:.1f}h.\n\n"
                    "If your original bot host is back up, don't forget to "
                    "turn Maintenance 🔴 OFF so it doesn't conflict."
                )
                await db.bots.update_one(
                    {"bot_id": bot_doc["bot_id"]}, {"$set": {"maintenance_reminder_at": now}}
                )
    except asyncio.CancelledError:
        pass


async def main():
    setup_logging()

    master = Client(
        "master_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
    )

    # Register every handler module on the master bot.
    admin.register(master)
    bots.register(master)
    messages.register(master)
    maintenance.register(master)
    buttons.register(master)
    preview.register(master)
    stats.register(master)
    broadcast.register(master)
    export.register(master)
    backup.register(master)
    force_sub.register(master)
    ban.register(master)
    settings.register(master)

    await init_indexes()
    # Bug fix: these caches (added admins, toggled settings) were being
    # written to MongoDB correctly on every add/remove/toggle, but nothing
    # ever loaded them back on startup — so every process restart silently
    # reset "Additional Admins" to none and every Settings toggle back to
    # its default, even though the DB still had the real values.
    await load_admins()
    await load_settings()

    await master.start()
    logger.info("Master bot started")
    await set_bot_commands_list(master)
    bot_manager.attach_notifier(master, OWNER_ID)

    await load_and_start_bots()
    health_runner = await start_health_server()
    reminder_task = asyncio.create_task(maintenance_reminder_loop())
    keepalive_task = asyncio.create_task(keep_alive_loop(PORT))

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down...")
        reminder_task.cancel()
        keepalive_task.cancel()
        for bot_id in list(bot_manager.clients.keys()):
            await bot_manager.stop_bot(bot_id)
        await master.stop()
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
