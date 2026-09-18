"""Direct Telegram Bot API (HTTP) helpers, used for anything that only needs
to SEND a message — never receive/poll updates.

Why this exists: sending via api.telegram.org/bot<token>/sendX has no
"single consumer" restriction the way getUpdates/webhooks or a live MTProto
session does. It's exactly what any external script can safely do with a bot
token without ever conflicting with wherever that bot's real update-receiver
is hosted. Broadcast uses this instead of a live Pyrogram client, so it
works even when BotControl isn't currently "connected" to that bot (i.e.
Maintenance/Go Live are both off because the bot is being hosted, and its
updates are being polled, somewhere else entirely).
"""
import logging
import os

import aiohttp

logger = logging.getLogger("botcontrol")

_API_BASE = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = aiohttp.ClientTimeout(total=30)

_MEDIA_METHOD = {
    "photo": "sendPhoto",
    "video": "sendVideo",
    "document": "sendDocument",
    "animation": "sendAnimation",
}


async def _post_json(token: str, method: str, payload: dict) -> tuple[bool, dict]:
    url = _API_BASE.format(token=token, method=method)
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                return bool(data.get("ok")), data
    except Exception as e:
        logger.warning(f"Telegram API call {method} failed: {e}")
        return False, {"ok": False, "description": str(e)}


async def get_chat(token: str, chat_id) -> tuple[bool, dict]:
    return await _post_json(token, "getChat", {"chat_id": chat_id})


async def get_me(token: str) -> tuple[bool, dict]:
    return await _post_json(token, "getMe", {})


async def get_chat_member(token: str, chat_id, user_id: int) -> tuple[bool, dict]:
    return await _post_json(token, "getChatMember", {"chat_id": chat_id, "user_id": user_id})


async def export_chat_invite_link(token: str, chat_id) -> tuple[bool, dict]:
    return await _post_json(token, "exportChatInviteLink", {"chat_id": chat_id})


def buttons_to_markup(buttons: list) -> dict | None:
    """Converts our stored [[{"text","url"}, ...], ...] format into the raw
    inline_keyboard dict the HTTP Bot API expects."""
    if not buttons:
        return None
    kb = [[{"text": b["text"], "url": b["url"]} for b in row] for row in buttons if row]
    return {"inline_keyboard": kb} if kb else None


async def send_message(token: str, chat_id: int, text: str, reply_markup: dict = None) -> tuple[bool, dict]:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _post_json(token, "sendMessage", payload)


async def send_media_by_file_id(token: str, chat_id: int, media_type: str, file_id: str,
                                 caption: str = None, reply_markup: dict = None) -> tuple[bool, dict]:
    method = _MEDIA_METHOD.get(media_type)
    if not method:
        return False, {"ok": False, "description": f"unknown media_type {media_type}"}
    field = media_type
    payload = {"chat_id": chat_id, field: file_id}
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _post_json(token, method, payload)


async def send_content(token: str, chat_id: int, content: dict, buttons: list = None) -> tuple[bool, dict]:
    """content is our stored {"text","media_type","file_id","caption"} shape.
    Falls back to plain text if sending the media fails for any reason
    (e.g. a stale/foreign file_id) and text is available."""
    markup = buttons_to_markup(buttons or [])
    text = content.get("text") or ""
    media_type = content.get("media_type")
    file_id = content.get("file_id")
    caption = content.get("caption") or text or None

    if media_type and file_id:
        ok, data = await send_media_by_file_id(token, chat_id, media_type, file_id, caption, markup)
        if ok:
            return ok, data
        if text:
            logger.warning(f"send_content media failed, falling back to text: {data}")
            return await send_message(token, chat_id, text, markup)
        return ok, data

    return await send_message(token, chat_id, text or "Welcome!", markup)


async def upload_media_for_file_id(token: str, staging_chat_id: int, media_type: str,
                                    file_path: str) -> str | None:
    """Uploads a local file to `staging_chat_id` via THIS bot's own token,
    to obtain a file_id that is valid for this specific bot (a file_id
    minted by a different bot/session can't be reused directly). Returns
    the new file_id, or None on failure."""
    method = _MEDIA_METHOD.get(media_type)
    if not method:
        return None
    url = _API_BASE.format(token=token, method=method)
    try:
        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("chat_id", str(staging_chat_id))
            data.add_field(media_type, f, filename=os.path.basename(file_path))
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(url, data=data) as resp:
                    result = await resp.json()
    except Exception as e:
        logger.warning(f"upload_media_for_file_id failed: {e}")
        return None

    if not result.get("ok"):
        logger.warning(f"upload_media_for_file_id: Telegram rejected upload: {result}")
        return None

    obj = result["result"].get(media_type)
    if media_type == "photo" and isinstance(obj, list):
        obj = obj[-1] if obj else None  # largest size
    return obj.get("file_id") if obj else None
