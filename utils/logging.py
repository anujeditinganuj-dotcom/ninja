import logging
import re

_TOKEN_PATTERN = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,45}")


class RedactTokenFilter(logging.Filter):
    """Strips anything that looks like a Telegram bot token from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        if _TOKEN_PATTERN.search(msg):
            record.msg = _TOKEN_PATTERN.sub("[REDACTED]", msg)
            record.args = ()
        return True


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.addFilter(RedactTokenFilter())
    # Quiet down noisy third-party loggers
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
