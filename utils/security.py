"""Token encryption and masking helpers.

If ENCRYPTION_KEY is set (a Fernet key, generate one with
`python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
bot tokens are encrypted at rest in MongoDB. If it is not set, tokens are
stored as-is (not recommended for production).
"""
import logging

from cryptography.fernet import Fernet, InvalidToken

from config import ENCRYPTION_KEY

logger = logging.getLogger("botcontrol")

_fernet = None
if ENCRYPTION_KEY:
    try:
        _fernet = Fernet(ENCRYPTION_KEY.encode())
    except Exception:
        logger.error("Invalid ENCRYPTION_KEY provided; tokens will be stored unencrypted.")
        _fernet = None


def encrypt_token(token: str) -> str:
    if not _fernet:
        return token
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    if not _fernet:
        return token
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        # Token was stored unencrypted (e.g. before ENCRYPTION_KEY was set)
        return token


def is_encryption_enabled() -> bool:
    return _fernet is not None


def mask_token(token: str) -> str:
    if ":" in token:
        head = token.split(":", 1)[0]
        return f"{head}:****"
    return "****"
