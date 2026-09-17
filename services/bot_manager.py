import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import Message

from config import API_ID, API_HASH
from database import db
from services import ban_service, statistics

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

            force_sub = bot_doc.get("force_sub") or {}
            if force_sub.get("enabled") and user:
                is_member = await self._check_membership(client, force_sub.get("channel"), user.id)
                if not is_member:
                    await self._send_force_sub_prompt(client, chat_id, force_sub)
                    return

            if bot_doc.get("maintenance_mode"):
                content = bot_doc.get("maintenance_message") or {}
            else:
                content = bot_doc.get("normal_message") or {}

            await self._send_content(client, chat_id, content, bot_doc.get("buttons", []))
        except Exception as e:
            logger.error(f"Error processing start for bot {bot_id}: {e}")

    async def _check_membership(self, client: Client, channel: str, user_id: int) -> bool:
        if not channel:
            return True
        try:
            member = await client.get_chat_member(channel, user_id)
            status = str(member.status.value if hasattr(member.status, "value") else member.status).lower()
            return status not in ("left", "kicked", "banned")
        except RPCError as e:
            # Fail open: if the bot isn't an admin of the channel yet, or the
            # user simply hasn't interacted with it, don't lock everyone out.
            logger.warning(f"Force-sub membership check failed for {channel}: {e}")
            return True
        except Exception as e:
            logger.warning(f"Force-sub membership check error for {channel}: {e}")
            return True

    async def _send_force_sub_prompt(self, client: Client, chat_id: int, force_sub: dict) -> None:
        from keyboards.inline import join_channel_keyboard

        channel = force_sub.get("channel") or ""
        invite_link = force_sub.get("invite_link") or f"https://t.me/{channel.lstrip('@')}"
        try:
            await client.send_message(
                chat_id,
                "🔒 Please join our channel to use this bot, then tap **I've Joined**.",
                reply_markup=join_channel_keyboard(invite_link),
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
