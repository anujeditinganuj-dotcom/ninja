from pyrogram import Client, enums, filters
from pyrogram.types import CallbackQuery, Message

import logging

from database import db
from keyboards.inline import bot_panel_keyboard, message_type_keyboard, photo_type_keyboard
from services.bot_manager import bot_manager
from services.message_service import set_message, set_welcome_photo
from utils.state import RESERVED_COMMANDS, clear_state, get_state, set_state
from services.admin_service import is_admin
UNAUTHORIZED = "❌ You are not authorized to use this control panel."


logger = logging.getLogger(__name__)

NOT_CONNECTED = (
    "⚠️ This bot isn't connected right now, so the {kind} couldn't be cached for it "
    "(a file sent to this panel only works for the bot that's live and running).\n\n"
    "Reconnect it, then resend the {kind}."
)



def register(app: Client) -> None:
    @app.on_callback_query(filters.regex(r"^bot_message:(-?\d+)$"))
    async def bot_message_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await cq.message.edit_text("✏️ **Edit Message**\n\nChoose which message to edit:",
                                    reply_markup=message_type_keyboard(bot_id))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^setmsg_(normal|maint):(-?\d+)$"))
    async def setmsg_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        kind_raw, bot_id = cq.matches[0].group(1), int(cq.matches[0].group(2))
        kind = "normal" if kind_raw == "normal" else "maintenance"
        set_state(cq.from_user.id, "awaiting_message", {"bot_id": bot_id, "kind": kind})
        await cq.message.edit_text(
            "✏️ Send the new message now.\n\n"
            "You can send plain text, or a photo/video/document/animation with a caption.\n"
            "HTML formatting supported: <b>bold</b>, <i>italic</i>, <u>underline</u>, <s>strike</s>\n\n"
            "🙈 <b>Hide/Spoiler text</b> (tap to reveal):\n"
            "<code>&lt;tg-spoiler&gt;hidden text&lt;/tg-spoiler&gt;</code>\n\n"
            "Example: Price: <code>&lt;tg-spoiler&gt;₹75 only&lt;/tg-spoiler&gt;</code>\n\n"
            "Send /cancel to abort.",
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^bot_photospoiler:(-?\d+)$"))
    async def bot_photospoiler_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer("Unauthorized.", show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        current = (bot_doc or {}).get("photo_spoiler", False)
        new_val  = not current
        await db.bots.update_one({"bot_id": bot_id}, {"$set": {"photo_spoiler": new_val}})
        status = "ON 🌫️ — Photos will appear blurred until tapped." if new_val else "OFF — Photos will show normally."
        await cq.answer(f"Blur Photo: {status}", show_alert=True)
        await cq.message.edit_reply_markup(
            reply_markup=bot_panel_keyboard(bot_id, photo_spoiler=new_val)
        )

    @app.on_callback_query(filters.regex(r"^bot_blur:(-?\d+)$"))
    async def bot_blur_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer("Unauthorized.", show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        set_state(cq.from_user.id, "awaiting_blur_text", {"bot_id": bot_id})
        await cq.message.edit_text(
            "🙈 <b>Blur Text Setup</b>\n\n"
            "Send the text you want to <b>hide/blur</b>.\n\n"
            "<b>Option 1 — Blur entire text:</b>\n"
            "Just send any text normally.\n\n"
            "<b>Option 2 — Blur specific lines only:</b>\n"
            "Start a line with <code>#</code> to blur just that line.\n\n"
            "Example:\n"
            "<code>🔥 Hot content available!\n"
            "# ₹499/month — tap to reveal\n"
            "📩 DM to buy</code>\n\n"
            "The <code>#</code> line will be blurred, others stay visible.\n"
            "Users will see it blurred — tap to reveal.\n\n"
            "Example: <code>₹75 only 🔥</code>\n\n"
            "The text will be saved and shown as spoiler in your welcome message.\n\n"
            "Send /cancel to abort.",
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()

    @app.on_message(
        filters.private
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_blur_text")
    )
    async def receive_blur_text(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return
        state  = get_state(message.from_user.id)
        bot_id = state["data"]["bot_id"]
        clear_state(message.from_user.id)

        raw = message.text or message.caption or ""
        if not raw.strip():
            return await message.reply_text("Please send some text to blur.")

        # If any line starts with #, wrap ONLY those lines in spoiler.
        # Lines without # stay visible. This lets admins write:
        #   Normal visible line
        #   # This line will be blurred
        #   Another visible line
        lines = raw.split("\n")
        if any(line.lstrip().startswith("#") for line in lines):
            processed = []
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    # Remove the # prefix and wrap in spoiler
                    spoiler_text = stripped[1:].lstrip()
                    processed.append(f"<tg-spoiler>{spoiler_text}</tg-spoiler>")
                else:
                    processed.append(line)
            blurred = "\n".join(processed)
        else:
            # No # prefix — wrap entire text in spoiler (original behavior)
            blurred = f"<tg-spoiler>{raw}</tg-spoiler>"

        # Preserve existing media/photo — only update the caption/text
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        existing = (bot_doc or {}).get("normal_message", {}) or {}
        existing_media_type = existing.get("media_type")
        existing_file_id    = existing.get("file_id")
        existing_text       = existing.get("text", "") or ""

        # Bug fix: this used to unconditionally append the new blurred text
        # to whatever text was already there ("existing_text + blurred"),
        # so applying Blur Text a second time kept the FIRST blur block too
        # — the two runs together instead of the new one replacing the old.
        # Fix: we track the exact block we appended last time
        # (last_blur_block) and strip it back off the base text before
        # appending the new one, so re-applying blur replaces rather than
        # stacks. First-ever application (no last_blur_block yet) behaves
        # as before — append to whatever base welcome text already existed.
        last_block = (bot_doc or {}).get("last_blur_block")
        base_text = existing_text
        if last_block:
            if base_text == last_block:
                base_text = ""
            elif base_text.endswith("\n" + last_block):
                base_text = base_text[: -(len(last_block) + 1)]

        combined = (base_text + "\n" + blurred).strip() if base_text else blurred

        from services.message_service import set_message
        await set_message(
            bot_id, "normal",
            text=combined,
            media_type=existing_media_type,
            file_id=existing_file_id,
            caption=combined,
        )
        await db.bots.update_one({"bot_id": bot_id}, {"$set": {"last_blur_block": blurred}})

        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        await message.reply_text(
            f"✅ Blur text saved!\n\n"
            f"Preview: <tg-spoiler>{raw}</tg-spoiler>\n\n"
            f"Users will see this blurred in the welcome message.",
            parse_mode=enums.ParseMode.HTML,
            reply_markup=bot_panel_keyboard(bot_id),
        )

    @app.on_callback_query(filters.regex(r"^bot_photo:(-?\d+)$"))
    async def bot_photo_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        bot_id = int(cq.matches[0].group(1))
        await cq.message.edit_text(
            "🖼 **Edit Photo**\n\nChoose which message this photo applies to:\n\n"
            "⚠️ If Maintenance is currently ON, users are seeing the "
            "**Maintenance** message — set the photo there for it to actually show up.",
            reply_markup=photo_type_keyboard(bot_id),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^delphoto_(normal|maint):(-?\d+)$"))
    async def delphoto_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        kind_raw, bot_id = cq.matches[0].group(1), int(cq.matches[0].group(2))
        kind = "normal" if kind_raw == "normal" else "maintenance"
        label = "Normal" if kind == "normal" else "Maintenance"

        from services.message_service import remove_welcome_photo
        removed = await remove_welcome_photo(bot_id, kind)
        if not removed:
            return await cq.answer(f"{label} message has no photo set.", show_alert=True)

        await cq.answer(f"✅ {label} photo removed.", show_alert=True)
        await cq.message.edit_text(
            "🖼 **Edit Photo**\n\nChoose which message this photo applies to:\n\n"
            "⚠️ If Maintenance is currently ON, users are seeing the "
            "**Maintenance** message — set the photo there for it to actually show up.",
            reply_markup=photo_type_keyboard(bot_id),
        )

    @app.on_callback_query(filters.regex(r"^setphoto_(normal|maint):(-?\d+)$"))
    async def setphoto_cb(client: Client, cq: CallbackQuery):
        if not is_admin(cq.from_user.id):
            return await cq.answer(UNAUTHORIZED, show_alert=True)
        kind_raw, bot_id = cq.matches[0].group(1), int(cq.matches[0].group(2))
        kind = "normal" if kind_raw == "normal" else "maintenance"
        set_state(cq.from_user.id, "awaiting_welcome_photo", {"bot_id": bot_id, "kind": kind})
        label = "Normal" if kind == "normal" else "Maintenance"
        await cq.message.edit_text(
            f"🖼 Send a photo to use for the **{label}** message.\n\n"
            "Existing text for that message will be kept as the caption.\n\nSend /cancel to abort."
        )
        await cq.answer()

    @app.on_message(
        filters.private
        & filters.photo
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_welcome_photo")
    )
    async def receive_welcome_photo(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id, kind = state["data"]["bot_id"], state["data"]["kind"]
        clear_state(message.from_user.id)

        cached_id = await bot_manager.recache_media(
            bot_id, "photo", message.photo.file_id, client, message.from_user.id
        )
        if cached_id is None:
            # recache failed — managed bot may not be connected or DM blocked.
            # Try saving the master bot's file_id directly as a best-effort
            # fallback (it may work if the bot shares the same DC as the master).
            logger.warning(
                f"recache_media failed for bot {bot_id} — "
                f"falling back to master bot file_id (may not work across DCs)"
            )
            cached_id = message.photo.file_id

        await set_welcome_photo(bot_id, kind, cached_id)
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        label = "Normal" if kind == "normal" else "Maintenance"
        await message.reply_text(
            f"✅ {label} photo updated for @{bot_doc['username']}.",
            reply_markup=bot_panel_keyboard(bot_id),
        )

    @app.on_message(
        filters.private
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_welcome_photo")
        & ~filters.photo
        & ~filters.command(RESERVED_COMMANDS)
    )
    async def welcome_photo_wrong_type(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return
        await message.reply_text("Please send a photo, or /cancel to abort.")

    @app.on_message(
        filters.private
        & ~filters.command(RESERVED_COMMANDS)
        & filters.create(lambda _, __, m: (get_state(m.from_user.id) or {}).get("action") == "awaiting_message")
    )
    async def receive_message_content(client: Client, message: Message):
        if not is_admin(message.from_user.id):
            return
        state = get_state(message.from_user.id)
        bot_id, kind = state["data"]["bot_id"], state["data"]["kind"]
        clear_state(message.from_user.id)

        text = media_type = file_id = caption = None
        if message.photo:
            media_type, file_id, caption = "photo", message.photo.file_id, message.caption
        elif message.video:
            media_type, file_id, caption = "video", message.video.file_id, message.caption
        elif message.document:
            media_type, file_id, caption = "document", message.document.file_id, message.caption
        elif message.animation:
            media_type, file_id, caption = "animation", message.animation.file_id, message.caption
        else:
            text = message.text or message.caption or ""

        if media_type:
            cached_id = await bot_manager.recache_media(bot_id, media_type, file_id, client, message.from_user.id)
            if cached_id is None:
                return await message.reply_text(NOT_CONNECTED.format(kind=media_type))
            file_id = cached_id

        await set_message(bot_id, kind, text=text, media_type=media_type, file_id=file_id, caption=caption)
        if kind == "normal":
            await db.bots.update_one({"bot_id": bot_id}, {"$unset": {"last_blur_block": ""}})

        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        label = "Normal" if kind == "normal" else "Maintenance"
        await message.reply_text(
            f"✅ {label} message updated for @{bot_doc['username']}.",
            reply_markup=bot_panel_keyboard(bot_id),
        )
