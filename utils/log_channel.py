"""Posts bot lifecycle / new-user events to an admin log channel, the same
way many bot panels give the owner a live feed without having to open the
control panel. All sending goes through the *master* bot client (it's the
one the owner made an admin of the log channel), never a managed bot.
"""
import logging

from pyrogram import Client
from pyrogram.enums import ParseMode

logger = logging.getLogger("botcontrol")

_client: Client | None = None
_channel_id: int | None = None


def attach(client: Client, channel_id: int | None) -> None:
    """Called once from main.py after the master bot starts."""
    global _client, _channel_id
    _client = client
    _channel_id = channel_id


async def log_event(text: str) -> None:
    if not _client or not _channel_id:
        return
    try:
        await _client.send_message(_channel_id, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"log_channel: failed to post event: {e}")
