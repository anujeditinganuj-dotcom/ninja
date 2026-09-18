"""Wraps every outgoing message/caption in a Telegram <blockquote> — applied
once, globally, by patching pyrogram.Client's send/edit methods. Message.reply_text
and Message.edit_text delegate to these same Client methods internally, so this
one patch covers the master control bot's own UI *and* every managed bot's
/start, maintenance, and force-sub replies, without touching each handler.

Call apply_blockquote_patch() once, before any Client is created or started
(main.py does this at import time).
"""

import functools
import html as _html

from pyrogram import Client
from pyrogram.errors import MessageNotModified

# method_name -> index of the `text` arg within *args (after self, chat_id)
_TEXT_ARG_INDEX = {
    "send_message": 1,          # (self, chat_id, text, ...)
    "edit_message_text": 2,     # (self, chat_id, message_id, text, ...)
}
# these only ever receive `caption` as a keyword in this codebase
_CAPTION_METHODS = ("send_photo", "send_video", "send_document", "send_animation")

_patched = False


def BQ(text):
    """Escape then wrap text in a Telegram HTML blockquote. None/empty text
    passes through unchanged so media-only sends with no caption still work."""
    if not text:
        return text
    return f"<blockquote>{_html.escape(str(text), quote=False)}</blockquote>"


def _wrap_positional_or_kw(orig, param_name, arg_index, swallow_not_modified=False):
    @functools.wraps(orig)
    async def wrapper(self, *args, **kwargs):
        args = list(args)
        if param_name in kwargs:
            kwargs[param_name] = BQ(kwargs[param_name])
        elif len(args) > arg_index:
            args[arg_index] = BQ(args[arg_index])
        try:
            return await orig(self, *args, **kwargs)
        except MessageNotModified:
            # Bug fix: every "refresh this same menu" callback (bot_settings,
            # bot_stats, stats_menu, etc.) calls message.edit_text() with
            # content that's often byte-for-byte what's already on screen —
            # e.g. tapping a button that's already showing that panel, or two
            # taps landing in quick succession. Telegram then rejects the
            # edit with MESSAGE_NOT_MODIFIED, which used to propagate up and
            # crash the whole CallbackQueryHandler (visible in logs as an
            # "Unexpected exception raised" traceback) — the cq.answer()
            # right after the edit_text call never ran, so the button's
            # loading spinner stayed stuck for the admin. Since the message
            # already shows the exact content being requested, that's a
            # harmless no-op: swallow it here so the handler carries on to
            # its cq.answer() as normal, only for edit_message_text (the
            # error doesn't apply to send_message, which always creates a
            # new message).
            if not swallow_not_modified:
                raise
            return None
    return wrapper


def _wrap_kwarg_only(orig, param_name):
    @functools.wraps(orig)
    async def wrapper(self, *args, **kwargs):
        if param_name in kwargs:
            kwargs[param_name] = BQ(kwargs[param_name])
        return await orig(self, *args, **kwargs)
    return wrapper


def apply_blockquote_patch() -> None:
    global _patched
    if _patched:
        return

    for method_name, arg_index in _TEXT_ARG_INDEX.items():
        orig = getattr(Client, method_name)
        swallow = method_name == "edit_message_text"
        setattr(Client, method_name, _wrap_positional_or_kw(orig, "text", arg_index, swallow_not_modified=swallow))

    for method_name in _CAPTION_METHODS:
        orig = getattr(Client, method_name)
        setattr(Client, method_name, _wrap_kwarg_only(orig, "caption"))

    _patched = True
