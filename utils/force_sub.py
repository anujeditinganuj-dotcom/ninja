"""Shared helpers for the multi-channel Force-Subscribe feature.

Force-sub used to store a single channel per bot:
    {"enabled": bool, "channel": ..., "invite_link": ..., "title": ...}

It now supports a list of channels:
    {"enabled": bool, "channels": [{"channel": ..., "invite_link": ..., "title": ...}, ...]}

normalize_force_sub() is the single place that understands both shapes, so
every handler and service works off the same normalized dict and old bots
in the database keep working without a migration script.
"""


def normalize_force_sub(raw: dict | None) -> dict:
    """Returns {"enabled": bool, "channels": [{"channel", "invite_link", "title"}, ...]}."""
    raw = raw or {}
    if "channels" in raw:
        channels = [dict(c) for c in (raw.get("channels") or [])]
    elif raw.get("channel"):
        # Legacy single-channel doc — lift it into the new list shape.
        channels = [{
            "channel": raw["channel"],
            "invite_link": raw.get("invite_link"),
            "title": raw.get("title"),
        }]
    else:
        channels = []
    return {"enabled": bool(raw.get("enabled")) and bool(channels), "channels": channels}


def channel_label(entry: dict) -> str:
    """Human-readable label for a single channel entry, for menus and prompts.
    Shows only the title/username — never the numeric chat ID."""
    channel = entry.get("channel")
    title   = entry.get("title")
    if title:
        return title
    # Public @username — readable enough on its own
    if isinstance(channel, str) and channel.startswith("@"):
        return channel
    # Numeric ID only — nothing user-friendly to show; fall back to "Channel"
    return "Channel"
