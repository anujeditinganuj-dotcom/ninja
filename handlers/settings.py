import time

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from keyboards.inline import (
    admin_access_keyboard,
    back_keyboard,
    settings_admin_keyboard,
    settings_botmgmt_keyboard,
    settings_database_keyboard,
    settings_main_keyboard,
    settings_notifications_keyboard,
    settings_security_keyboard,
)
from services.admin_service import is_owner_id, list_added_admins, add_admin, remove_admin
from services.activity_log import log_action, get_recent_logs
from services.bot_manager import bot_manager
from services.settings_service import all_values, toggle as toggle_setting
from utils.security import is_encryption_enabled
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state

UNAUTHORIZED = "❌ You are not authorized to use this control panel."

# Settings is a control surface for the whole panel — including who else
# gets admin access — so unlike most other features it's kept owner-only,
# not delegated to added admins (see Settings → Security → Access Control
# for the *bot-operation* delegation toggle instead).
is_owner = is_owner_id


def settings_home_text() -> str:
    return (
        "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "       ⚙️ SETTINGS\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "Manage your BotControl Manager preferences.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Admin — owner ID & who else can manage the panel\n"
        "🤖 Bot Management — reconnect & startup behaviour\n"
        "🔔 Notifications — what the owner gets DM'd about\n"
        "🔐 Security — token protection, access control, audit log\n"
        "🗄️ Database — connection status & storage info"
    )


async def show_settings_menu(client: Client, chat_id: int, user_id: int) -> None:
    if not is_owner(user_id):
        await client.send_message(chat_id, UNAUTHORIZED)
        return
    await client.send_message(chat_id, settings_home_text(), reply_markup=settings_main_keyboard())


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex("^settings_menu$"))
    async def settings_menu_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        clear_state(cq.from_user.id)
        await cq.message.edit_text(settings_home_text(), reply_markup=settings_main_keyboard())
        await cq.answer()

    # ── 👤 Admin ─────────────────────────────────────────────────────
    @app.on_callback_query(filters.regex("^settings_admin$"))
    async def settings_admin_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        added = list_added_admins()
        text = (
            "👤 **ADMIN**\n\n"
            f"🆔 Owner ID: `{OWNER_ID}` (you — full access, can't be changed here)\n\n"
            f"🔐 Additional Admins: {len(added)}\n"
            "These can use every bot-operation feature (broadcast, ban, "
            "messages, connect) but never Settings itself."
        )
        await cq.message.edit_text(text, reply_markup=settings_admin_keyboard())
        await cq.answer()

    @app.on_callback_query(filters.regex("^admin_access_menu$"))
    async def admin_access_menu_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        added = list_added_admins()
        lines = "\n".join(f"• `{uid}`" for uid in added) or "_No additional admins yet._"
        await cq.message.edit_text(
            f"🔐 **Admin Access**\n\n{lines}",
            reply_markup=admin_access_keyboard(added),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^admin_add$"))
    async def admin_add_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        set_state(cq.from_user.id, "awaiting_admin_id")
        await cq.message.edit_text(
            "➕ **Add Admin**\n\n"
            "Send the numeric Telegram user ID to grant admin access.\n\n"
            "Send /cancel to abort.",
            reply_markup=back_keyboard("admin_access_menu"),
        )
        await cq.answer()

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_admin_id")
    )
    async def receive_admin_id(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        clear_state(message.from_user.id)
        raw = message.text.strip()
        if not raw.lstrip("-").isdigit():
            return await message.reply_text("❌ That's not a valid numeric user ID.")
        new_id = int(raw)
        if new_id == OWNER_ID:
            return await message.reply_text("That's already you — the owner always has full access.")
        added = await add_admin(new_id)
        if not added:
            return await message.reply_text("⚠️ That user is already an admin.")
        await log_action(message.from_user.id, "add_admin", f"user_id={new_id}")
        added_admins = list_added_admins()
        lines = "\n".join(f"• `{uid}`" for uid in added_admins)
        await message.reply_text(
            f"✅ `{new_id}` added as an admin.\n\n🔐 **Admin Access**\n\n{lines}",
            reply_markup=admin_access_keyboard(added_admins),
        )

    @app.on_callback_query(filters.regex(r"^admin_remove:(-?\d+)$"))
    async def admin_remove_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        target_id = int(cq.matches[0].group(1))
        removed = await remove_admin(target_id)
        if removed:
            await log_action(cq.from_user.id, "remove_admin", f"user_id={target_id}")
        added = list_added_admins()
        lines = "\n".join(f"• `{uid}`" for uid in added) or "_No additional admins yet._"
        await cq.message.edit_text(f"🔐 **Admin Access**\n\n{lines}", reply_markup=admin_access_keyboard(added))
        await cq.answer("Removed." if removed else "Already removed.", show_alert=True)

    # ── 🤖 Bot Management ────────────────────────────────────────────
    @app.on_callback_query(filters.regex("^settings_botmgmt$"))
    async def settings_botmgmt_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await cq.message.edit_text(
            "🤖 **BOT MANAGEMENT**\n\n"
            "🔄 Auto Reconnect — restart a bot automatically if it drops\n"
            "🚀 Auto Start Bots — reconnect eligible bots when the process boots\n"
            "🟢 Default: Maintenance — should a newly connected bot start in "
            "Maintenance mode?",
            reply_markup=settings_botmgmt_keyboard(all_values()),
        )
        await cq.answer()

    # ── 🔔 Notifications ─────────────────────────────────────────────
    @app.on_callback_query(filters.regex("^settings_notifications$"))
    async def settings_notifications_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await cq.message.edit_text(
            "🔔 **NOTIFICATIONS**\n\n"
            "⚠️ Error Alerts — reconnect/start failures\n"
            "🔴 Bot Offline Alerts — watchdog auto-restart notices\n"
            "📊 Daily Statistics — a combined stats digest once every 24h",
            reply_markup=settings_notifications_keyboard(all_values()),
        )
        await cq.answer()

    # ── 🔐 Security ──────────────────────────────────────────────────
    @app.on_callback_query(filters.regex("^settings_security$"))
    async def settings_security_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await cq.message.edit_text(
            "🔐 **SECURITY**\n\n"
            "🔑 Token Protection — whether ENCRYPTION_KEY is set (env-based, "
            "tap for details)\n"
            "🛡️ Access Control — when ON, only the real owner can disconnect "
            "a bot, restore a backup, or manage admins\n"
            "📋 Activity Logs — recent owner/admin actions",
            reply_markup=settings_security_keyboard(all_values(), is_encryption_enabled()),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^setting_info_token$"))
    async def setting_info_token_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        if is_encryption_enabled():
            msg = "🟢 ENCRYPTION_KEY is set — bot tokens are encrypted at rest in the database."
        else:
            msg = (
                "🔴 ENCRYPTION_KEY is NOT set — bot tokens are stored in PLAIN TEXT.\n\n"
                "Set the ENCRYPTION_KEY environment variable and restart to enable this."
            )
        await cq.answer(msg, show_alert=True)

    @app.on_callback_query(filters.regex("^settings_activity_logs$"))
    async def settings_activity_logs_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        logs = await get_recent_logs(15)
        if not logs:
            body = "_No activity recorded yet._"
        else:
            lines = []
            for entry in logs:
                ts = time.strftime("%d %b, %H:%M", time.localtime(entry["ts"]))
                detail = f" — {entry['details']}" if entry.get("details") else ""
                lines.append(f"`{ts}` — `{entry['user_id']}` **{entry['action']}**{detail}")
            body = "\n".join(lines)
        await cq.message.edit_text(
            f"📋 **Activity Logs** (last {len(logs)})\n\n{body}",
            reply_markup=back_keyboard("settings_security"),
        )
        await cq.answer()

    # ── 🗄️ Database ──────────────────────────────────────────────────
    @app.on_callback_query(filters.regex("^settings_database$"))
    async def settings_database_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await cq.message.edit_text(
            "🗄️ **DATABASE**\n\nChoose what to check:",
            reply_markup=settings_database_keyboard(),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^settings_db_status$"))
    async def settings_db_status_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        start = time.perf_counter()
        try:
            await db.command("ping")
            latency_ms = (time.perf_counter() - start) * 1000
            status_line = f"🟢 Connected ({latency_ms:.0f} ms)"
        except Exception as e:
            status_line = f"🔴 Connection error: {e}"

        bots_count = await db.bots.count_documents({})
        users_count = await db.bot_users.count_documents({})
        banned_count = await db.banned_users.count_documents({})
        admins_count = await db.admins.count_documents({})

        await cq.message.edit_text(
            "📊 **Database Status**\n\n"
            f"{status_line}\n\n"
            f"🤖 Bots: {bots_count}\n"
            f"👥 Bot Users: {users_count}\n"
            f"🚫 Banned Users: {banned_count}\n"
            f"🔐 Extra Admins: {admins_count}",
            reply_markup=back_keyboard("settings_database"),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^settings_db_info$"))
    async def settings_db_info_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        try:
            stats = await db.command("dbStats")
            data_mb = stats.get("dataSize", 0) / (1024 * 1024)
            storage_mb = stats.get("storageSize", 0) / (1024 * 1024)
            index_mb = stats.get("indexSize", 0) / (1024 * 1024)
            text = (
                "💾 **Data Information**\n\n"
                f"Database: `{stats.get('db', '—')}`\n"
                f"Collections: {stats.get('collections', '—')}\n"
                f"Documents: {stats.get('objects', '—')}\n\n"
                f"📦 Data Size: {data_mb:.2f} MB\n"
                f"🗜 Storage Size: {storage_mb:.2f} MB\n"
                f"📇 Index Size: {index_mb:.2f} MB"
            )
        except Exception as e:
            text = f"💾 **Data Information**\n\n🔴 Could not fetch stats: {e}"
        await cq.message.edit_text(text, reply_markup=back_keyboard("settings_database"))
        await cq.answer()

    # ── 📊 System Status / ℹ️ About (top-level, requested alongside the rest) ──
    @app.on_callback_query(filters.regex("^settings_system_status$"))
    async def settings_system_status_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bots = await db.bots.find().to_list(length=1000)
        total = len(bots)
        online = sum(1 for b in bots if bot_manager.is_running(b["bot_id"]))
        maint = sum(1 for b in bots if b.get("maintenance_mode"))
        live = sum(1 for b in bots if b.get("go_live"))
        await cq.message.edit_text(
            "📊 **System Status**\n\n"
            f"🤖 Total Bots: {total}\n"
            f"🟢 Online: {online}\n"
            f"🔴 Offline: {total - online}\n"
            f"🛠 In Maintenance: {maint}\n"
            f"🚀 Go Live: {live}\n"
            f"🔐 Token Encryption: {'ON' if is_encryption_enabled() else 'OFF'}",
            reply_markup=back_keyboard("settings_menu"),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^settings_about$"))
    async def settings_about_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await cq.message.edit_text(
            "ℹ️ **About**\n\n"
            "🤖 BotControl Manager\n"
            "Connect, customize, and maintain unlimited Telegram bots from "
            "one master panel.\n\n"
            "One master bot • Independent control for every connected bot.",
            reply_markup=back_keyboard("settings_menu"),
        )
        await cq.answer()

    # ── toggles (shared by Bot Management / Notifications / Security) ──
    @app.on_callback_query(filters.regex(r"^setting_toggle:(\w+)$"))
    async def setting_toggle_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        key = cq.matches[0].group(1)
        new_val = await toggle_setting(key)
        await log_action(cq.from_user.id, "toggle_setting", f"{key}={new_val}")

        values = all_values()
        if key in ("auto_reconnect", "auto_start_bots", "default_maintenance_on_connect"):
            await cq.message.edit_reply_markup(settings_botmgmt_keyboard(values))
        elif key in ("notify_errors", "notify_offline", "notify_daily_stats"):
            await cq.message.edit_reply_markup(settings_notifications_keyboard(values))
        elif key == "restrict_destructive_to_owner":
            await cq.message.edit_reply_markup(settings_security_keyboard(values, is_encryption_enabled()))
        await cq.answer(f"{'🟢 Enabled' if new_val else '🔴 Disabled'}.")
