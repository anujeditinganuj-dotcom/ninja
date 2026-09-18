import logging
import time

from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import CallbackQuery, Message

from config import API_HASH, API_ID, OWNER_ID
from database import db
from keyboards.inline import bot_panel_keyboard, bot_picker_keyboard, confirm_keyboard, dashboard_keyboard, my_bots_keyboard
from services.bot_manager import bot_manager
from utils.security import encrypt_token
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state
from utils.validators import is_valid_bot_token
from services.admin_service import is_admin, can_do_destructive
from services.settings_service import get as get_setting
UNAUTHORIZED = "❌ You are not authorized to use this control panel."


logger = logging.getLogger("botcontrol")


async def start_connect_flow(client: Client, source) -> None:
    user_id = source.from_user.id
    set_state(user_id, "awaiting_bot_token")
    text = "➕ **Connect Bot**\n\nPlease send the bot token you received from @BotFather.\n\nSend /cancel to abort."
    if isinstance(source, CallbackQuery):
        # source.message may be the photo dashboard — edit_text() on a photo
        # message edits its caption, not the message body. Replace it
        # outright instead (see help_menu in admin.py for the same fix).
        try:
            await source.message.delete()
        except Exception:
            pass
        await client.send_message(source.message.chat.id, text)
    else:
        await source.reply_text(text)


async def _my_bots_text_and_markup():
    bots = await db.bots.find().to_list(length=500)
    if not bots:
        return "🤖 **Connected Bots**\n\nNo bots connected yet. Use ➕ Connect Bot to add one.", dashboard_keyboard()
    lines = "\n".join(f"{i + 1}. @{b['username']}" for i, b in enumerate(bots))
    return f"🤖 **Connected Bots**\n\n{lines}", my_bots_keyboard(bots)


async def show_my_bots(client: Client, chat_id: int) -> None:
    text, markup = await _my_bots_text_and_markup()
    await client.send_message(chat_id, text, reply_markup=markup)


async def edit_to_my_bots(client: Client, cq: CallbackQuery) -> None:
    text, markup = await _my_bots_text_and_markup()
    # cq.message may be the photo dashboard — edit_text() on a photo message
    # edits its caption (1024-char cap), which breaks once the bot list
    # grows. Replace it outright instead (same fix as help_menu).
    try:
        await cq.message.delete()
    except Exception:
        pass
    await client.send_message(cq.message.chat.id, text, reply_markup=markup)


async def build_bot_panel_text(bot_doc: dict) -> str:
    status = "🟢 Active" if bot_manager.is_running(bot_doc["bot_id"]) else "🔴 Offline"
    maint = "🟢 ON" if bot_doc.get("maintenance_mode") else "🔴 OFF"
    live = "🚀 ON" if bot_doc.get("go_live") else "➖ OFF"
    normal = bot_doc.get("normal_message") or {}
    maintenance = bot_doc.get("maintenance_message") or {}
    btn_count = sum(len(row) for row in bot_doc.get("buttons", []))

    normal_msg = "✅ Text" + (" + 🖼️ Photo" if normal.get("file_id") else "") if (normal.get("text") or normal.get("file_id")) else "❌ Not set"
    maint_msg = "✅ Text" + (" + 🖼️ Photo" if maintenance.get("file_id") else "") if (maintenance.get("text") or maintenance.get("file_id")) else "❌ Not set"

    active_kind = "Maintenance" if bot_doc.get("maintenance_mode") else "Normal"

    return (
        f"🤖 @{bot_doc['username']}\n\n"
        f"Status: {status}\n"
        f"Maintenance: {maint}\n"
        f"Go Live (Full-time): {live}\n"
        f"Buttons: {btn_count}\n\n"
        f"Normal Message: {normal_msg}\n"
        f"Maintenance Message: {maint_msg}\n\n"
        f"👀 Users currently see: **{active_kind}** message"
    )


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex("^connect_bot$"))
    async def connect_bot_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await start_connect_flow(client, cq)
        await cq.answer()

    @app.on_callback_query(filters.regex("^my_bots$"))
    async def my_bots_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await edit_to_my_bots(client, cq)
        await cq.answer()

    @app.on_callback_query(filters.regex("^delete_bot_menu$"))
    async def delete_bot_menu_cb(client: Client, cq: CallbackQuery):
        if not can_do_destructive(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bots = await db.bots.find().to_list(length=500)
        if not bots:
            return await cq.answer("No bots connected.", show_alert=True)
        await cq.message.edit_text(
            "🗑 **Delete Bot**\n\nChoose which bot to delete:",
            reply_markup=bot_picker_keyboard(bots, "bot_disconnect"),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_select:(-?\d+)$"))
    async def bot_select_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        text = await build_bot_panel_text(bot_doc)
        await cq.message.edit_text(text, reply_markup=bot_panel_keyboard(bot_id))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_disconnect:(-?\d+)$"))
    async def bot_disconnect_cb(client: Client, cq: CallbackQuery):
        if not can_do_destructive(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        await cq.message.edit_text(
            f"⚠️ Are you sure you want to disconnect @{bot_doc['username']}?\n\n"
            "All configuration for this bot may be removed.",
            reply_markup=confirm_keyboard(f"disconnect_confirm:{bot_id}", f"bot_select:{bot_id}"),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^disconnect_confirm:(-?\d+)$"))
    async def disconnect_confirm_cb(client: Client, cq: CallbackQuery):
        if not can_do_destructive(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await bot_manager.stop_bot(bot_id)
        await db.bots.delete_one({"bot_id": bot_id})
        await db.bot_users.delete_many({"bot_id": bot_id})
        await db.banned_users.delete_many({"bot_id": bot_id})
        await cq.answer("Bot disconnected.", show_alert=True)
        await edit_to_my_bots(client, cq)

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_bot_token")
    )
    async def receive_token(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return
        token = message.text.strip()
        if not is_valid_bot_token(token):
            await message.reply_text("❌ Invalid bot token.\n\nPlease send a valid BotFather token.")
            return

        token_id = token.split(":")[0]
        existing = await db.bots.find_one({"token_id": token_id})
        if existing:
            clear_state(message.from_user.id)
            await message.reply_text(
                "⚠️ This bot is already connected.\n\nOpen its management panel?",
                reply_markup=confirm_keyboard(f"bot_select:{existing['bot_id']}", "back_dashboard"),
            )
            return

        verify_client = Client(name=f"verify_{token_id}", api_id=API_ID, api_hash=API_HASH,
                                bot_token=token, in_memory=True)
        try:
            await verify_client.start()
            me = await verify_client.get_me()
        except RPCError:
            await message.reply_text("❌ Invalid bot token.\n\nPlease send a valid BotFather token.")
            return
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            await message.reply_text("❌ Invalid bot token.\n\nPlease send a valid BotFather token.")
            return
        finally:
            try:
                await verify_client.stop()
            except Exception:
                pass

        set_state(message.from_user.id, "confirm_connect", {
            "token": token,
            "bot_id": me.id,
            "username": me.username,
            "first_name": me.first_name,
        })
        await message.reply_text(
            f"✅ Bot Connected\n\n"
            f"Name: {me.first_name}\n"
            f"Username: @{me.username}\n"
            f"ID: {me.id}\n\n"
            "Would you like to enable management for this bot?",
            reply_markup=confirm_keyboard("confirm_connect_yes", "confirm_connect_no"),
        )

    @app.on_callback_query(filters.regex("^confirm_connect_no$"))
    async def confirm_connect_no(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        clear_state(cq.from_user.id)
        await cq.message.edit_text("Cancelled.", reply_markup=dashboard_keyboard())
        await cq.answer()

    @app.on_callback_query(filters.regex("^confirm_connect_yes$"))
    async def confirm_connect_yes(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state = get_state(cq.from_user.id)
        if not state or state["action"] != "confirm_connect":
            return await cq.answer("Session expired, please send the token again.", show_alert=True)
        data = state["data"]
        clear_state(cq.from_user.id)

        now = int(time.time())
        maintenance_default = get_setting("default_maintenance_on_connect")
        bot_doc = {
            "bot_id": data["bot_id"],
            "username": data["username"],
            "first_name": data["first_name"],
            "token": encrypt_token(data["token"]),
            "token_id": data["token"].split(":")[0],
            "enabled": True,
            "maintenance_mode": maintenance_default,
            "maintenance_since": now if maintenance_default else None,
            "go_live": False,
            "normal_message": {
                "text": "🎉 Welcome!\n\nUse the buttons below to continue.",
                "media_type": None, "file_id": None, "caption": None,
            },
            "maintenance_message": {
                "text": "🔧 This bot is currently under maintenance.\n\nPlease try again later.",
                "media_type": None, "file_id": None, "caption": None,
            },
            "buttons": [],
            "created_at": now,
            "updated_at": now,
        }
        await db.bots.update_one({"bot_id": data["bot_id"]}, {"$set": bot_doc}, upsert=True)

        if maintenance_default:
            # Settings → Bot Management → Default: Maintenance was saving
            # maintenance_mode=True to the DB but never actually starting the
            # bot, so it sat there claiming to be in Maintenance while still
            # fully offline. Bring it live now to match what was configured.
            runtime_doc = dict(bot_doc)
            runtime_doc["token"] = data["token"]
            ok, msg = await bot_manager.start_bot(runtime_doc)
            if ok:
                await cq.answer(
                    "Bot connected and live in 🛠 Maintenance mode (Settings → Default: Maintenance is ON).",
                    show_alert=True,
                )
            else:
                logger.error(f"Failed to start bot @{data['username']} with default maintenance on: {msg}")
                await cq.answer(
                    f"Bot saved, but starting it failed: {msg}\n\nOpen its panel to retry.",
                    show_alert=True,
                )
        else:
            # Safe default: don't connect yet. BotControl only goes live once
            # you turn on Maintenance (while your own host is down) or Go
            # Live (Full-time), so there's never an accidental
            # TelegramConflictError against your original bot host.
            await cq.answer(
                "Bot connected! It's saved but not live yet — turn on 🛠 Maintenance "
                "when your own host is down, or 🚀 Go Live for full-time hosting.",
                show_alert=True,
            )

        text = await build_bot_panel_text(bot_doc)
        await cq.message.edit_text(text, reply_markup=bot_panel_keyboard(data["bot_id"]))
