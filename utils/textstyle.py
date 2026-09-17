"""Small-caps unicode text styling, shared by button labels (keyboards/inline.py)
and plain message bodies (e.g. the welcome/help text in handlers/admin.py)."""

_SC_MAP = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ", "g": "ɢ",
    "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ",
    "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "s", "t": "ᴛ", "u": "ᴜ",
    "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
}


def SC(text: str) -> str:
    """Convert ASCII letters in text to small-caps unicode; leaves emoji,
    digits, box-drawing characters and punctuation untouched."""
    return "".join(_SC_MAP.get(ch.lower(), ch) if ch.isalpha() else ch for ch in text)
