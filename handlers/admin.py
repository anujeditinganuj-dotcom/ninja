from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from keyboards.inline import back_keyboard, dashboard_keyboard
from services.bot_manager import bot_manager
from utils.state import clear_state
from utils.textstyle import SC

UNAUTHORIZED = "❌ You are not authorized to use this control panel."

WELCOME_PHOTO_URL = "https://iili.io/nojMW67.jpg"

WELCOME_TEXT = SC(
    "🤖 BOTCONTROL MANAGER\n\n"
    "Welcome to your Professional Telegram Bot Management Panel.\n\n"
    "⚡ Connect multiple Telegram bots\n"
    "🎨 Set custom messages for every bot\n"
    "🛠 Enable/disable maintenance mode, or Go Live full-time\n"
    "🔘 Add custom inline buttons\n"
    "🖼️ Add photos, videos & media\n"
    "📢 Broadcast to a bot's users\n"
    "🔒 Force-Subscribe to one or more channels\n"
    "📥 Export users • 💾 Backup & Restore\n"
    "📊 Monitor users & combined bot statistics\n"
    "👥 Multi-admin access\n"
    "🔐 Secure, fully configurable admin panel\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "🚀 One Master Bot • Multiple Bots • Full Control\n\n"
    "Manage all your connected bots from one powerful dashboard.\n\n"
    "👇 Choose an option below to get started."
)

HELP_TEXT = SC(
    "❓ BOTCONTROL MANAGER — HELP\n\n"
    "Welcome to the complete bot management system.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "➕ CONNECT BOT\n"
    "Connect and manage multiple Telegram bots from one place.\n\n"
    "🤖 MY BOTS\n"
    "View all connected bots and open their individual control panel.\n\n"
    "✏️ CUSTOM MESSAGE\n"
    "Set a unique welcome or maintenance message for each bot.\n\n"
    "🛠 MAINTENANCE MODE\n"
    "Temporarily show a custom maintenance message to users, or turn on "
    "🚀 Go Live to host a bot full-time.\n\n"
    "🖼️ MEDIA SUPPORT\n"
    "Add photos, videos, documents and captions to your messages.\n\n"
    "🔘 INLINE BUTTONS\n"
    "Create custom buttons with your preferred URLs and layouts.\n\n"
    "📢 BROADCAST\n"
    "Send a message to every user who has started a given bot.\n\n"
    "🔒 FORCE-SUBSCRIBE\n"
    "Require users to join one or more channels before a bot replies.\n\n"
    "👀 PREVIEW\n"
    "Preview exactly what users will receive before enabling it.\n\n"
    "📊 STATISTICS\n"
    "Per-bot stats, plus combined totals across every connected bot.\n\n"
    "📥 EXPORT USERS\n"
    "Download a bot's user list as a CSV file.\n\n"
    "💾 BACKUP & RESTORE\n"
    "Export every bot's configuration to JSON, and restore it with /restore.\n\n"
    "⚙️ BOT SETTINGS\n"
    "Manage individual bot configuration and preferences.\n\n"
    "🗑️ DISCONNECT BOT\n"
    "Safely remove a connected bot from your management panel.\n\n"
    "🚫 BAN / UNBAN\n"
    "Silently block specific users from a bot, or lift the block.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "⚙️ SETTINGS\n"
    "Panel-wide preferences: Admin Management (grant others access), "
    "Bot Management, Notifications, Security & audit log, Database status, "
    "System Status and About.\n\n"
    "🔐 SECURITY\n"
    "Only the authorized owner (and any admins you add) can access the "
    "control panel. Bot tokens and sensitive credentials must never be exposed.\n\n"
    "⚡ BOTCONTROL MANAGER\n"
    "One Master Bot • Multiple Bots • Complete Control"
)


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def build_dashboard_text() -> str:
    total = await db.bots.count_documents({})
    online = sum(1 for bot_id in bot_manager.clients)
    maintenance = await db.bots.count_documents({"maintenance_mode": True})
    offline = max(total - online, 0)
    return (
        "╭─────────────────────────╮\n"
        "│   🤖 BOTCONTROL MANAGER │\n"
        "╰─────────────────────────╯\n\n"
        f"🤖 Connected Bots: {total}\n"
        f"🟢 Online: {online}\n"
        f"🔴 Offline: {offline}\n"
        f"🛠 Maintenance: {maintenance}\n\n"
        "Choose an action:"
    )


async def send_dashboard(client: Client, chat_id: int) -> None:
    """Sends the welcome photo with the dashboard text as its caption —
    used for /start and every "« Back" that returns to the main dashboard."""
    text = await build_dashboard_text()
    caption = f"{WELCOME_TEXT}\n\n{text}"
    await client.send_photo(chat_id, WELCOME_PHOTO_URL, caption=caption, reply_markup=dashboard_keyboard())


def register(app: Client) -> None:
    @app.on_message(filters.private & filters.command(["start", "help", "bots", "mybots", "connect", "stats", "settings"]))
    async def commands(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            await message.reply_text(UNAUTHORIZED)
            return
        clear_state(message.from_user.id)
        cmd = message.command[0].lower()

        if cmd == "start":
            await send_dashboard(client, message.chat.id)
        elif cmd == "help":
            await message.reply_text(HELP_TEXT, reply_markup=back_keyboard("back_dashboard"))
        elif cmd in ("bots", "mybots"):
            from handlers.bots import show_my_bots
            await show_my_bots(client, message.chat.id)
        elif cmd == "connect":
            from handlers.bots import start_connect_flow
            await start_connect_flow(client, message)
        elif cmd == "stats":
            from handlers.stats import show_overview_stats
            await show_overview_stats(client, message.chat.id)
        elif cmd == "settings":
            from handlers.settings import show_settings_menu
            await show_settings_menu(client, message.chat.id, message.from_user.id)

    @app.on_message(filters.private & filters.command("cancel"))
    async def cancel_cmd(client: Client, message: Message):
        clear_state(message.from_user.id)
        await message.reply_text("Operation cancelled.")

    @app.on_callback_query(filters.regex("^back_dashboard$"))
    async def back_dashboard(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        clear_state(cq.from_user.id)
        # The dashboard is now a photo message, so a text screen (Help,
        # Settings, a bot panel, ...) can't be turned into it via edit_text —
        # replace it outright instead.
        try:
            await cq.message.delete()
        except Exception:
            pass
        await send_dashboard(client, cq.message.chat.id)
        await cq.answer()

    @app.on_callback_query(filters.regex("^help_menu$"))
    async def help_menu(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        # The dashboard is a photo message, so edit_text() on it edits the
        # caption (1024-char limit) instead of message text (4096-char
        # limit) — HELP_TEXT is longer than 1024 chars, which triggers
        # MEDIA_CAPTION_TOO_LONG. Replace the message instead, same as
        # back_dashboard does.
        try:
            await cq.message.delete()
        except Exception:
            pass
        await client.send_message(
            cq.message.chat.id, HELP_TEXT, reply_markup=back_keyboard("back_dashboard")
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^(message_menu|buttons_menu)$"))
    async def generic_redirect(client: Client, cq: CallbackQuery):
        # These live on the main dashboard but are per-bot settings, so route
        # the owner to My Bots first to pick which bot to configure.
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        from handlers.bots import edit_to_my_bots
        await edit_to_my_bots(client, cq)
        await cq.answer()
