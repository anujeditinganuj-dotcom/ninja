import time

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from config import OWNER_ID
from database import db
from handlers.bots import build_bot_panel_text
from keyboards.inline import back_keyboard, bot_panel_keyboard, bulk_maintenance_keyboard, maintenance_keyboard
from services.bot_manager import bot_manager
from utils.security import decrypt_token

UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _status_text(bot_doc: dict) -> str:
    maint = "🟢 ON" if bot_doc.get("maintenance_mode") else "🔴 OFF"
    live = "🚀 ON" if bot_doc.get("go_live") else "➖ OFF"
    since_line = ""
    if bot_doc.get("maintenance_mode") and bot_doc.get("maintenance_since"):
        elapsed = time.time() - bot_doc["maintenance_since"]
        since_line = f"On for: {_format_duration(elapsed)}\n"
    return (
        f"🛠 **Maintenance Mode**\n\n"
        f"Bot: @{bot_doc['username']}\n"
        f"Maintenance: {maint}\n"
        f"{since_line}"
        f"Go Live (Full-time): {live}\n\n"
        "🟢 **Enable** — BotControl connects right now and shows your "
        "maintenance message. Use this while your own bot host is down.\n"
        "🔴 **Disable** — BotControl disconnects completely so your "
        "original host can run without a conflict.\n"
        "🚀 **Go Live** — keeps BotControl connected permanently, "
        "regardless of the toggle above (for power users who want "
        "BotControl to be the full-time host)."
    )


async def _connect(bot_id: int, bot_doc: dict) -> tuple[bool, str]:
    if bot_manager.is_running(bot_id):
        return True, "already running"
    runtime_doc = dict(bot_doc)
    runtime_doc["token"] = decrypt_token(bot_doc["token"])
    return await bot_manager.start_bot(runtime_doc)


async def _set_maintenance(bot_id: int, bot_doc: dict, new_val: bool) -> tuple[bool, str]:
    """Applies the maintenance toggle for one bot: updates the DB
    (including the on-since / reminder timestamps), connects or
    disconnects as needed, and returns (ok, message)."""
    now = int(time.time())
    updates = {"maintenance_mode": new_val}
    if new_val:
        if not bot_doc.get("maintenance_since"):
            updates["maintenance_since"] = now
        updates["maintenance_reminder_at"] = now
    else:
        updates["maintenance_since"] = None
        updates["maintenance_reminder_at"] = None
    await db.bots.update_one({"bot_id": bot_id}, {"$set": updates})
    bot_doc.update(updates)

    if new_val:
        ok, msg = await _connect(bot_id, bot_doc)
        return ok, ("live" if ok else msg)
    else:
        if not bot_doc.get("go_live"):
            await bot_manager.stop_bot(bot_id)
            return True, "disconnected"
        return True, "still live (Go Live is on)"


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_maintenance:(-?\d+)$"))
    async def maintenance_menu(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        await cq.message.edit_text(_status_text(bot_doc), reply_markup=maintenance_keyboard(bot_id, bot_doc))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^maint_(on|off):(-?\d+)$"))
    async def maintenance_toggle(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state, bot_id = cq.matches[0].group(1), int(cq.matches[0].group(2))
        new_val = state == "on"
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)

        ok, detail = await _set_maintenance(bot_id, bot_doc, new_val)
        if new_val:
            alert = "Maintenance enabled — BotControl is now live." if ok else \
                f"Maintenance enabled, but failed to connect: {detail}"
        else:
            alert = "Maintenance disabled — BotControl has disconnected." if detail == "disconnected" \
                else "Maintenance disabled."

        await cq.answer(alert, show_alert=True)
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        text = await build_bot_panel_text(bot_doc)
        await cq.message.edit_text(text, reply_markup=bot_panel_keyboard(bot_id))

    @app.on_callback_query(filters.regex(r"^golive_(on|off):(-?\d+)$"))
    async def go_live_toggle(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state, bot_id = cq.matches[0].group(1), int(cq.matches[0].group(2))
        new_val = state == "on"
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)

        await db.bots.update_one({"bot_id": bot_id}, {"$set": {"go_live": new_val}})
        bot_doc["go_live"] = new_val

        if new_val:
            ok, msg = await _connect(bot_id, bot_doc)
            alert = "Go Live enabled — BotControl is now the full-time host." if ok else \
                f"Go Live enabled, but failed to connect: {msg}"
        else:
            if bot_doc.get("maintenance_mode"):
                alert = "Go Live disabled."
            else:
                await bot_manager.stop_bot(bot_id)
                alert = "Go Live disabled — BotControl has disconnected."

        await cq.answer(alert, show_alert=True)
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        await cq.message.edit_text(_status_text(bot_doc), reply_markup=maintenance_keyboard(bot_id, bot_doc))

    # ---- Bulk maintenance (all bots at once) ----

    @app.on_callback_query(filters.regex("^bulk_maintenance_menu$"))
    async def bulk_menu(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        total = await db.bots.count_documents({})
        on_count = await db.bots.count_documents({"maintenance_mode": True})
        text = (
            "🛠 **Maintenance — All Bots**\n\n"
            f"Connected bots: {total}\n"
            f"Currently in Maintenance: {on_count}\n\n"
            "Use this when *all* your bots' original hosts go down together "
            "(e.g. your server is offline), instead of toggling each one by one. "
            "Or open a single bot from 🤖 My Bots to manage it individually."
        )
        # cq.message may be the photo dashboard — edit_text() on a photo
        # message edits its caption (1024-char cap), not the message body.
        # Replace it outright instead (same fix as help_menu in admin.py).
        try:
            await cq.message.delete()
        except Exception:
            pass
        await client.send_message(cq.message.chat.id, text, reply_markup=bulk_maintenance_keyboard())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bulk_maint_(on|off)$"))
    async def bulk_toggle(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        new_val = cq.matches[0].group(1) == "on"
        await cq.answer("Working on it…")

        bots = await db.bots.find().to_list(length=10000)
        ok_count = fail_count = 0
        for bot_doc in bots:
            ok, _ = await _set_maintenance(bot_doc["bot_id"], bot_doc, new_val)
            if ok:
                ok_count += 1
            else:
                fail_count += 1

        summary = (
            f"✅ Maintenance turned {'ON' if new_val else 'OFF'} for {ok_count} bot(s)."
            + (f"\n⚠️ {fail_count} bot(s) failed to connect." if fail_count else "")
        )
        await cq.message.edit_text(summary, reply_markup=back_keyboard("back_dashboard"))
