import re

from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from database import db
from handlers.bots import build_bot_panel_text
from keyboards.inline import bot_panel_keyboard, force_sub_keyboard
from services.bot_manager import bot_manager
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state

UNAUTHORIZED = "❌ You are not authorized to use this control panel."
CHANNEL_ID_RE = re.compile(r"^-?\d+$")


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_forcesub:(-?\d+)$"))
    async def force_sub_menu(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        fs = bot_doc.get("force_sub") or {}
        status = f"🟢 ON ({fs.get('channel')})" if fs.get("enabled") else "🔴 OFF"
        await cq.message.edit_text(
            f"🔒 **Force-Subscribe**\n\nBot: @{bot_doc['username']}\nCurrent Status: {status}\n\n"
            "When enabled, users must join the configured channel before receiving the start message. "
            "The managed bot must be an **admin** of that channel to verify membership.",
            reply_markup=force_sub_keyboard(bot_id),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^fs_enable:(-?\d+)$"))
    async def fs_enable_start(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_fs_channel", {"bot_id": bot_id})
        await cq.message.edit_text(
            "Send the channel username (e.g. @mychannel) or its numeric ID "
            "(e.g. -1003925649805, for private channels).\n\n"
            "⚠️ Make the managed bot an **admin** of that channel first, otherwise membership "
            "checks will fail open (users won't be blocked).\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_fs_channel")
    )
    async def fs_receive_channel(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id = state["data"]["bot_id"]
        raw = message.text.strip()
        clear_state(message.from_user.id)

        if CHANNEL_ID_RE.match(raw):
            # Numeric channel ID (e.g. -1003925649805) — used for private
            # channels that have no @username. Do NOT prefix with "@".
            channel = int(raw)
            channel_display = raw
            invite_link = None  # no t.me/<username> link possible for a bare ID
        else:
            channel = raw if raw.startswith("@") else f"@{raw}"
            channel_display = channel
            invite_link = f"https://t.me/{channel.lstrip('@')}"

        warning = ""
        managed_client = bot_manager.clients.get(bot_id)
        if managed_client:
            try:
                chat = await managed_client.get_chat(channel)
                me = await managed_client.get_me()
                member = await managed_client.get_chat_member(channel, me.id)
                status = str(member.status.value if hasattr(member.status, "value") else member.status).lower()
                is_admin = status in ("administrator", "creator", "owner")
                if not is_admin:
                    warning = (
                        f"\n\n⚠️ @{me.username} is not an admin of {channel_display} yet — membership checks "
                        "will fail open until you add it as admin there."
                    )
                if getattr(chat, "invite_link", None):
                    invite_link = chat.invite_link
                elif invite_link is None and is_admin:
                    # Private channel (numeric ID) with no existing invite link
                    # yet — generate one since the bot is admin.
                    try:
                        invite_link = await managed_client.export_chat_invite_link(channel)
                    except RPCError:
                        pass
            except RPCError as e:
                warning = f"\n\n⚠️ Could not verify the channel ({e}). Saved anyway — double-check the ID/username."
        else:
            warning = "\n\n⚠️ This bot isn't currently running, so the channel couldn't be verified yet."

        if not invite_link:
            warning += (
                "\n\n⚠️ No invite link could be generated (private channel, bot not verified as admin yet). "
                "Users won't see a join button until this is resolved — re-run this step once the bot is admin."
            )

        await db.bots.update_one(
            {"bot_id": bot_id},
            {"$set": {"force_sub": {"enabled": True, "channel": channel, "invite_link": invite_link}}},
        )
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        await message.reply_text(
            f"✅ Force-Subscribe enabled for @{bot_doc['username']} → {channel_display}{warning}",
            reply_markup=bot_panel_keyboard(bot_id),
        )

    @app.on_callback_query(filters.regex(r"^fs_disable:(-?\d+)$"))
    async def fs_disable(client: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await db.bots.update_one({"bot_id": bot_id}, {"$set": {"force_sub.enabled": False}})
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        await cq.answer("Force-Subscribe disabled.", show_alert=True)
        text = await build_bot_panel_text(bot_doc)
        await cq.message.edit_text(text, reply_markup=bot_panel_keyboard(bot_id))
