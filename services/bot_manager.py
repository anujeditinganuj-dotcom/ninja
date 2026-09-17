import asyncio
import logging
import os

from pyrogram import Client, filters
from pyrogram.errors import RPCError, UserNotParticipant
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import Message

from config import API_ID, API_HASH
from database import db
from services import ban_service, statistics
from utils.force_sub import channel_label, normalize_force_sub

logger = logging.getLogger("botcontrol")

HEALTH_CHECK_INTERVAL = 60  # seconds
ADMIN_STATUSES = {"administrator", "creator", "owner"}


class BotManager:
    """Owns one live Pyrogram Client per connected managed bot and keeps it
    running independently: starting, stopping, restarting-on-crash, all
    without touching the master bot or any other managed bot.
    """

    def __init__(self):
        self.clients: dict[int, Client] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._watchdogs: dict[int, asyncio.Task] = {}
        self._notifier_client: Client | None = None
        self._owner_id: int | None = None

    def attach_notifier(self, client: Client, owner_id: int) -> None:
        """Lets the manager DM the owner (via the master bot) about things
        that happen in the background: a managed bot failing to connect, or
        crashing and failing to auto-recover."""
        self._notifier_client = client
        self._owner_id = owner_id

    async def notify_owner(self, text: str) -> None:
        if not self._notifier_client or not self._owner_id:
            return
        try:
            await self._notifier_client.send_message(self._owner_id, text)
        except Exception as e:
            logger.warning(f"Failed to notify owner: {e}")

    def _lock(self, bot_id: int) -> asyncio.Lock:
        if bot_id not in self._locks:
            self._locks[bot_id] = asyncio.Lock()
        return self._locks[bot_id]

    def is_running(self, bot_id: int) -> bool:
        return bot_id in self.clients

    async def start_bot(self, bot_doc: dict) -> tuple[bool, str]:
        """bot_doc must contain a *decrypted* token."""
        bot_id = bot_doc["bot_id"]
        async with self._lock(bot_id):
            if bot_id in self.clients:
                return True, "already running"

            client = Client(
                name=f"managed_{bot_id}",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=bot_doc["token"],
                in_memory=True,
            )

            async def on_incoming(c: Client, m: Message):
                await self._handle_start(bot_id, c, m)

            async def on_recheck(c: Client, cq):
                await self._process_start(bot_id, c, cq.message.chat.id, cq.from_user)
                try:
                    await cq.answer()
                except Exception:
                    pass

            # While this bot is connected here (maintenance or full-time
            # hosting), every private message — not just /start — should get
            # the configured reply, since the user's real bot isn't around to
            # answer anything else either.
            client.add_handler(MessageHandler(on_incoming, filters.private))
            client.add_handler(CallbackQueryHandler(on_recheck, filters.regex("^fs_recheck$")))

            try:
                await client.start()
            except Exception as e:
                logger.error(f"Failed to start managed bot id={bot_id}: {e}")
                return False, str(e)

            self.clients[bot_id] = client
            self._watchdogs[bot_id] = asyncio.create_task(self._watchdog(bot_id))
            logger.info(f"Connected managed bot @{bot_doc.get('username', bot_id)}")
            return True, "started"

    async def stop_bot(self, bot_id: int) -> None:
        async with self._lock(bot_id):
            task = self._watchdogs.pop(bot_id, None)
            if task:
                task.cancel()
            client = self.clients.pop(bot_id, None)
            if client:
                try:
                    await client.stop()
                except Exception as e:
                    logger.warning(f"Error stopping bot {bot_id}: {e}")
                logger.info(f"Disconnected managed bot id={bot_id}")

    async def restart_bot(self, bot_id: int) -> None:
        await self.stop_bot(bot_id)
        bot_doc = await db.bots.find_one({"bot_id": bot_id})
        if bot_doc and bot_doc.get("enabled"):
            from utils.security import decrypt_token
            runtime_doc = dict(bot_doc)
            runtime_doc["token"] = decrypt_token(bot_doc["token"])
            ok, msg = await self.start_bot(runtime_doc)
            if not ok:
                await self.notify_owner(
                    f"⚠️ **Auto-recovery failed**\n\n"
                    f"@{bot_doc.get('username', bot_id)} crashed and could not "
                    f"be reconnected: {msg}\n\n"
                    "It's now offline — check its Maintenance/Go Live status "
                    "in the panel."
                )

    async def _handle_start(self, bot_id: int, client: Client, message: Message) -> None:
        is_start = bool(message.command) and message.command[0].lower() == "start"
        await self._process_start(bot_id, client, message.chat.id, message.from_user, is_start=is_start)

    async def _process_start(self, bot_id: int, client: Client, chat_id: int, user, is_start: bool = True) -> None:
        try:
            bot_doc = await db.bots.find_one({"bot_id": bot_id})
            if not bot_doc:
                return
            if user and await ban_service.is_banned(bot_id, user.id):
                # Banned users get no reply at all — not even an error —
                # so the bot appears completely unresponsive to them.
                return
            if user:
                if is_start:
                    await statistics.record_start(bot_id, user.id)
                else:
                    await statistics.record_seen(bot_id, user.id)

            force_sub = normalize_force_sub(bot_doc.get("force_sub"))
            if force_sub["enabled"] and user:
                unjoined = []
                for entry in force_sub["channels"]:
                    is_member = await self._check_membership(client, entry.get("channel"), user.id)
                    if not is_member:
                        unjoined.append(entry)
                if unjoined:
                    await self._send_force_sub_prompt(client, chat_id, unjoined)
                    return

            if bot_doc.get("maintenance_mode"):
                content = bot_doc.get("maintenance_message") or {}
            else:
                content = bot_doc.get("normal_message") or {}

            await self._send_content(client, chat_id, content, bot_doc.get("buttons", []))
        except Exception as e:
            logger.error(f"Error processing start for bot {bot_id}: {e}")

    async def _check_membership(self, client: Client, channel: str | int, user_id: int) -> bool:
        if not channel:
            return True
        try:
            member = await client.get_chat_member(channel, user_id)
            status = str(member.status.value if hasattr(member.status, "value") else member.status).lower()
            return status not in ("left", "kicked", "banned")
        except UserNotParticipant:
            # This is NOT a failure — it's Telegram's normal way of saying
            # "this user has never been in the channel", which is exactly
            # the case force-sub exists to catch. Must NOT fail open here.
            return False
        except RPCError as e:
            # Fail open: if the bot isn't an admin of the channel yet, or some
            # other real error occurs, don't lock everyone out.
            logger.warning(f"Force-sub membership check failed for {channel}: {e}")
            return True
        except Exception as e:
            logger.warning(f"Force-sub membership check error for {channel}: {e}")
            return True

    async def _send_force_sub_prompt(self, client: Client, chat_id: int, channels: list) -> None:
        from keyboards.inline import join_channel_keyboard

        buttons = []
        for entry in channels:
            channel = entry.get("channel") or ""
            invite_link = entry.get("invite_link")
            if not invite_link and isinstance(channel, str) and channel:
                # Only a @username channel can derive a t.me link this way; a
                # numeric channel ID has no username and must have its own
                # invite_link already saved (see handlers/force_sub.py).
                invite_link = f"https://t.me/{channel.lstrip('@')}"
            if not invite_link:
                logger.error(
                    "Force-sub prompt: no invite link available for channel %r, skipping its button",
                    channel,
                )
                continue
            buttons.append((channel_label(entry), invite_link))

        if not buttons:
            logger.error("Force-sub prompt skipped for chat %s: no channel had an invite link", chat_id)
            return
        try:
            await client.send_message(
                chat_id,
                "🔒 Please join the channel(s) below to use this bot, then tap **I've Joined**.",
                reply_markup=join_channel_keyboard(buttons),
            )
        except Exception as e:
            logger.error(f"Error sending force-sub prompt: {e}")

    async def _send_content(self, client: Client, chat_id: int, content: dict, buttons: list) -> None:
        from keyboards.inline import build_user_buttons

        markup = build_user_buttons(buttons)
        text = content.get("text") or ""
        media_type = content.get("media_type")
        file_id = content.get("file_id")
        caption = content.get("caption") or text or None

        try:
            if media_type == "photo" and file_id:
                await client.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
            elif media_type == "video" and file_id:
                await client.send_video(chat_id, file_id, caption=caption, reply_markup=markup)
            elif media_type == "document" and file_id:
                await client.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
            elif media_type == "animation" and file_id:
                await client.send_animation(chat_id, file_id, caption=caption, reply_markup=markup)
            else:
                await client.send_message(chat_id, text or "Welcome!", reply_markup=markup)
        except Exception as e:
            logger.error(f"Error sending content to chat {chat_id}: {e}")

    async def recache_media(self, bot_id: int, media_type: str, file_id: str,
                             source_client: Client, owner_id: int) -> str | None:
        """A file_id is only valid for the bot that originally received it —
        one captured via the master bot's chat (or another managed bot)
        can't be resent by THIS managed bot's own client; Telegram rejects
        it. To fix that, download the media once via source_client and
        re-upload it through this bot's own client (landing quietly in the
        owner's DM with that bot); the file_id on that new message IS valid
        for this bot going forward, so callers should store that one
        instead of the original.

        Returns the re-cached file_id, or None if this bot isn't currently
        connected or the re-upload failed — callers should treat None as
        "can't cache right now" rather than silently keep the invalid id.
        """
        client = self.clients.get(bot_id)
        if not client:
            return None
        send_fn = {
            "photo": client.send_photo,
            "video": client.send_video,
            "document": client.send_document,
            "animation": client.send_animation,
        }.get(media_type)
        if not send_fn:
            return None
        path = None
        try:
            path = await source_client.download_media(file_id)
            msg = await send_fn(owner_id, path)
            media_obj = getattr(msg, media_type, None)
            return media_obj.file_id if media_obj else None
        except Exception as e:
            logger.warning(f"Failed to recache {media_type} file_id for bot {bot_id}: {e}")
            return None
        finally:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    async def _watchdog(self, bot_id: int) -> None:
        """Periodically pings the managed bot's client; if it's unreachable,
        restarts only that bot without affecting the master bot or others.
        """
        try:
            while bot_id in self.clients:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                client = self.clients.get(bot_id)
                if not client:
                    break
                try:
                    await client.get_me()
                except Exception as e:
                    logger.warning(f"Bot {bot_id} health check failed ({e}); restarting")
                    bot_doc = await db.bots.find_one({"bot_id": bot_id})
                    uname = bot_doc.get("username", bot_id) if bot_doc else bot_id
                    await self.notify_owner(
                        f"🔁 **Reconnecting**\n\n@{uname} dropped ({e}). "
                        "Attempting an automatic restart…"
                    )
                    asyncio.create_task(self.restart_bot(bot_id))
                    break
        except asyncio.CancelledError:
            pass


bot_manager = BotManager()
