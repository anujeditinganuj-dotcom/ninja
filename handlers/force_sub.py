import re

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from database import db
from keyboards.inline import force_sub_menu_keyboard
from services import telegram_api
from utils.force_sub import channel_label, normalize_force_sub
from utils.security import decrypt_token
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state
from services.admin_service import is_admin
UNAUTHORIZED = "❌ You are not authorized to use this control panel."


CHANNEL_ID_RE = re.compile(r"^-?\d+$")



def _menu_text(bot_doc: dict, fs: dict) -> str:
    channels = fs["channels"]
    if not channels:
        status = "🔴 OFF (no channels added)"
    elif fs["enabled"]:
        status = f"🟢 ON — {len(channels)} channel(s)"
    else:
        status = f"⚪ Added ({len(channels)}) but disabled"
    listing = "\n".join(f"• {channel_label(c)}" for c in channels) or "—"
    return (
        f"🔒 **Force-Subscribe**\n\nBot: @{bot_doc['username']}\nStatus: {status}\n\n{listing}\n\n"
        "Users must join all channels below before getting the start message. "
        "The managed bot must be an **admin** of each channel to verify membership. "
        "Tap a channel to remove it."
    )


async def _show_menu(target, bot_id: int) -> None:
    """target: either a CallbackQuery (edits the message) or a Message (sends new)."""
    bot_doc = await db.bots.find_one({"bot_id": bot_id})
    if not bot_doc:
        return
    fs = normalize_force_sub(bot_doc.get("force_sub"))
    text = _menu_text(bot_doc, fs)
    markup = force_sub_menu_keyboard(bot_id, fs["channels"], fs["enabled"])
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)


async def _verify_channel(bot_id: int, channel, channel_display: str) -> tuple[str | None, str | None, str | None]:
    """Returns (invite_link, title, warning). Verified entirely over the
    bot's own HTTP API — works whether or not BotControl currently has a
    live connection to this bot."""
    invite_link = None if isinstance(channel, int) else f"https://t.me/{str(channel).lstrip('@')}"
    title = None
    warning = None

    bot_doc = await db.bots.find_one({"bot_id": bot_id})
    if not bot_doc:
        return invite_link, title, "\n\n⚠️ Bot not found."
    token = decrypt_token(bot_doc["token"])

    ok_chat, chat_data = await telegram_api.get_chat(token, channel)
    if not ok_chat:
        warning = f"\n\n⚠️ Could not verify the channel ({chat_data.get('description', 'unknown error')}). Saved anyway — double-check the ID/username."
    else:
        chat_result = chat_data.get("result", {})
        title = chat_result.get("title")
        if chat_result.get("invite_link"):
            invite_link = chat_result["invite_link"]

        ok_me, me_data = await telegram_api.get_me(token)
        me_username = me_data.get("result", {}).get("username") if ok_me else None
        me_id = me_data.get("result", {}).get("id") if ok_me else None

        is_admin = False
        if ok_me and me_id:
            ok_member, member_data = await telegram_api.get_chat_member(token, channel, me_id)
            if ok_member:
                status = member_data.get("result", {}).get("status", "")
                is_admin = status in ("administrator", "creator")
            else:
                warning = f"\n\n⚠️ Could not verify bot's admin status: {member_data.get('description', member_data)}"

        if not is_admin:
            warning = (warning or "") + (
                f"\n\n⚠️ @{me_username or 'the bot'} is not an admin of {channel_display} yet — "
                "membership checks will fail open until you add it as admin there."
            )
        elif invite_link is None:
            ok_link, link_data = await telegram_api.export_chat_invite_link(token, channel)
            if ok_link:
                invite_link = link_data.get("result")

    if not invite_link:
        extra = (
            "\n\n⚠️ No invite link could be generated (private channel, bot not verified as admin yet). "
            "Users won't see a join button for this channel until it's resolved."
        )
        warning = (warning or "") + extra
    return invite_link, title, warning


def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_forcesub:(-?\d+)$"))
    async def force_sub_menu(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        await _show_menu(cq, bot_id)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^fs_add:(-?\d+)$"))
    async def fs_add_start(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_fs_channel", {"bot_id": bot_id})
        await cq.message.edit_text(
            "Send the channel username (e.g. @mychannel) or its numeric ID "
            "(e.g. -1003925649805, for private channels) to add it to the list.\n\n"
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
        if not is_admin(message.from_user.id):
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
        else:
            channel = raw if raw.startswith("@") else f"@{raw}"
            channel_display = channel

        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await message.reply_text("Bot not found.")
        fs = normalize_force_sub(bot_doc.get("force_sub"))

        if any(str(c.get("channel")) == str(channel) for c in fs["channels"]):
            await message.reply_text(f"⚠️ {channel_display} is already in the list.")
            return await _show_menu(message, bot_id)

        invite_link, title, warning = await _verify_channel(bot_id, channel, channel_display)
        fs["channels"].append({"channel": channel, "invite_link": invite_link, "title": title})
        fs["enabled"] = True  # adding a channel is an explicit "turn it on" action

        await db.bots.update_one({"bot_id": bot_id}, {"$set": {"force_sub": fs}})
        await message.reply_text(f"✅ Added {channel_display} to Force-Subscribe.{warning or ''}")
        await _show_menu(message, bot_id)

    @app.on_callback_query(filters.regex(r"^fs_remove:(-?\d+):(\d+)$"))
    async def fs_remove(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        index = int(cq.matches[0].group(2))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        fs = normalize_force_sub(bot_doc.get("force_sub"))
        if 0 <= index < len(fs["channels"]):
            removed = fs["channels"].pop(index)
            if not fs["channels"]:
                fs["enabled"] = False
            await db.bots.update_one({"bot_id": bot_id}, {"$set": {"force_sub": fs}})
            await cq.answer(f"Removed {channel_label(removed)}.")
        else:
            await cq.answer("Already removed.")
        await _show_menu(cq, bot_id)

    @app.on_callback_query(filters.regex(r"^fs_toggle:(-?\d+)$"))
    async def fs_toggle(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if not bot_doc:
            return await cq.answer("Bot not found.", show_alert=True)
        fs = normalize_force_sub(bot_doc.get("force_sub"))
        if not fs["channels"]:
            return await cq.answer("Add a channel first.", show_alert=True)
        fs["enabled"] = not fs["enabled"]
        await db.bots.update_one({"bot_id": bot_id}, {"$set": {"force_sub": fs}})
        await cq.answer("Enabled." if fs["enabled"] else "Disabled.")
        await _show_menu(cq, bot_id)
