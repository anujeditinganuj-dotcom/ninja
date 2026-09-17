import asyncio
import logging
import os

import aiohttp

logger = logging.getLogger("botcontrol")

PING_INTERVAL = int(os.getenv("KEEPALIVE_INTERVAL", "600") or "600")  # seconds


def _ping_target(port: int) -> str:
    """Where to self-ping. Priority:
    1. PING_URL / HEALTHCHECK_URL / APP_URL — set explicitly
    2. RENDER_EXTERNAL_URL / RENDER_EXTERNAL_HOSTNAME — auto-set by Render
    3. Fallback: localhost on our own health-server port
    """
    for env_name in ("PING_URL", "HEALTHCHECK_URL", "APP_URL", "RENDER_EXTERNAL_URL"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value.rstrip("/")

    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip().strip("/")
    if render_host:
        return f"https://{render_host}"

    return f"http://127.0.0.1:{port}"


async def keep_alive_loop(port: int) -> None:
    """Self-pings the health endpoint ('/') every PING_INTERVAL seconds so
    free-tier hosts that spin down idle web services (Render's free plan
    sleeps after ~15 min of no inbound traffic) never see this one go idle.

    Harmless — and simply a no-op worth skipping — on paid/always-on plans
    or when self-hosting, since nothing there ever spins the process down.
    """
    if PING_INTERVAL <= 0:
        logger.info("Keep-alive disabled (KEEPALIVE_INTERVAL<=0).")
        return

    target = _ping_target(port)
    logger.info(f"Keep-alive ping target: {target} (every {PING_INTERVAL}s)")

    # Give the health server a moment to finish binding before the first ping.
    await asyncio.sleep(30)

    consecutive_failures = 0
    try:
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(
                        target, timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        if consecutive_failures:
                            logger.info(
                                f"Keep-alive ping recovered after "
                                f"{consecutive_failures} failure(s): {resp.status}"
                            )
                        else:
                            logger.debug(f"Keep-alive ping ok: {resp.status}")
                        consecutive_failures = 0
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    consecutive_failures += 1
                    # Early failures right after boot are normal — only warn
                    # once it's persisted for a few cycles.
                    if consecutive_failures >= 3:
                        logger.warning(f"Keep-alive ping failed ({consecutive_failures}x): {e}")
                    else:
                        logger.debug(f"Keep-alive ping failed (attempt {consecutive_failures}): {e}")

                await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        pass
