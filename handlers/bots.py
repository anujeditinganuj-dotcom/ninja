import logging
import time

from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import CallbackQuery, Message

from config import API_HASH, API_ID, OWNER_ID
from database import db
from keyboards.inline import bot_panel_keyboard, confirm_keyboard, dashboard_keyboard, my_bots_keyboard
from services.bot_manager import bot_manager
from utils.security import encrypt_token
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state
from utils.validators import is_valid_bot_token

logger = logging.getLogger("botcontrol")
UNAUTHORIZED = "❌ You are not authorized to use this control panel."


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def start_connect_flow(client: Client, source) -> None:
    user_id = source.from_user.id
    set_state(user_id, "awaiting_bot_token")
    text = "➕ **Connect Bot**\n\nPlease send the bot token you received from @BotFather.\n\nSend /cancel to abort."
    if isinstance(source, CallbackQuery):
        await source.message.edit_text(text)
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


async def edit_to_my_bots(cq: CallbackQuery) -> None:
    text, markup = await _my_bots_text_and_markup()
    await cq.message.edit_text(text, reply_markup=markup)


async def build_bot_panel_text(bot_doc: dict) -> str:
    status = "🟢 Active" if bot_manager.is_running(bot_doc["bot_id"]) else "🔴 Offline"
    maint = "🟢 ON" if bot_doc.get("maintenance_mode") else "🔴 OFF"
    live = "🚀 ON" if bot_doc.get("go_live") else "➖ OFF"
    normal = bot_doc.get("normal_message") or {}
    has_msg = "✅ Set" if (normal.get("text") or normal.get("file_id")) else "❌ Not set"
    btn_count = sum(len(row) for row in bot_doc.get("buttons", []))
    media = "🖼️ Set" if normal.get("file_id") else "➖ None"
    return (
        f"🤖 @{bot_doc['username']}\n\n"
        f"Status: {status}\n"
        f"Maintenance: {maint}\n"
        f"Go Live (Full-time): {live}\n"
        f"Custom Message: {has_msg}\n"
        f"Buttons: {btn_count}\n"
        f"Media: {media}"
    )


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex("^connect_bot$"))
    async def connect_bot_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await start_connect_flow(client, cq)
        await cq.answer()

    @app.on_callback_query(filters.regex("^my_bots$"))
    async def my_bots_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        await edit_to_my_bots(cq)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_select:(-?\d+)$"))
    async def bot_select_cb(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
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
        if not is_owner(cq.from_user.id):
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
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await bot_manager.stop_bot(bot_id)
        await db.bots.delete_one({"bot_id": bot_id})
        await db.bot_users.delete_many({"bot_id": bot_id})
        await db.banned_users.delete_many({"bot_id": bot_id})
        await cq.answer("Bot disconnected.", show_alert=True)
        await edit_to_my_bots(cq)

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_bot_token")
    )
    async def receive_token(client: Client, message: Message):
        if not is_owner(message.from_user.id):
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
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        clear_state(cq.from_user.id)
        await cq.message.edit_text("Cancelled.", reply_markup=dashboard_keyboard())
        await cq.answer()

    @app.on_callback_query(filters.regex("^confirm_connect_yes$"))
    async def confirm_connect_yes(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        state = get_state(cq.from_user.id)
        if not state or state["action"] != "confirm_connect":
            return await cq.answer("Session expired, please send the token again.", show_alert=True)
        data = state["data"]
        clear_state(cq.from_user.id)

        now = int(time.time())
        bot_doc = {
            "bot_id": data["bot_id"],
            "username": data["username"],
            "first_name": data["first_name"],
            "token": encrypt_token(data["token"]),
            "token_id": data["token"].split(":")[0],
            "enabled": True,
            "maintenance_mode": False,
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

        # Safe default: don't connect yet. BotControl only goes live once you
        # turn on Maintenance (while your own host is down) or Go Live
        # (Full-time), so there's never an accidental TelegramConflictError
        # against your original bot host.
        await cq.answer(
            "Bot connected! It's saved but not live yet — turn on 🛠 Maintenance "
            "when your own host is down, or 🚀 Go Live for full-time hosting.",
            show_alert=True,
        )

        text = await build_bot_panel_text(bot_doc)
        await cq.message.edit_text(text, reply_markup=bot_panel_keyboard(data["bot_id"]))
