import re

TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,45}$")
URL_RE = re.compile(r"^https?://\S+$")


def is_valid_bot_token(token: str) -> bool:
    return bool(TOKEN_RE.match(token.strip()))


def is_valid_url(url: str) -> bool:
    return bool(URL_RE.match(url.strip()))
