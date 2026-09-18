"""Small-caps unicode text styling, shared by button labels (keyboards/inline.py)
and plain message bodies (e.g. the welcome/help text in handlers/admin.py)."""

import re

_SC_MAP = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ", "g": "ɢ",
    "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ",
    "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "s", "t": "ᴛ", "u": "ᴜ",
    "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
}

# Anything that must stay literal ASCII to keep working: an HTML tag like
# <a href="..."> (Telegram's parser needs the real tag/attribute names, not
# small-caps look-alikes) or a {placeholder} token (calling code does a
# plain .replace()/.format() on the literal text, so it must still be
# spelled exactly "{first_name}" etc. after SC() runs, not a mangled copy).
_PROTECTED_RE = re.compile(r"<[^>]*>|\{[^{}]*\}")


def SC(text: str) -> str:
    """Convert ASCII letters in text to small-caps unicode; leaves emoji,
    digits, box-drawing characters and punctuation untouched. HTML tags and
    {placeholder} tokens are left completely as-is (see _PROTECTED_RE)."""
    def convert(segment: str) -> str:
        return "".join(_SC_MAP.get(ch.lower(), ch) if ch.isalpha() else ch for ch in segment)

    chunks = []
    pos = 0
    for m in _PROTECTED_RE.finditer(text):
        chunks.append(convert(text[pos:m.start()]))
        chunks.append(m.group())  # tag/placeholder — untouched
        pos = m.end()
    chunks.append(convert(text[pos:]))
    return "".join(chunks)
