from database import db

DEFAULTS: dict = {
    # 🤖 Bot Management
    "auto_reconnect": True,                    # watchdog auto-restarts a crashed managed bot
    "auto_start_bots": True,                   # reconnect eligible bots on process boot
    "default_maintenance_on_connect": False,   # new bot starts in Maintenance mode?
    # 🔔 Notifications
    "notify_errors": True,                     # DM owner on reconnect/start failures
    "notify_offline": True,                    # DM owner when a managed bot drops & is restarted
    "notify_daily_stats": False,                # send a once-a-day combined stats digest
    # 🔐 Security
    "restrict_destructive_to_owner": True,     # disconnect/restore/admin-mgmt: owner-only if True
}

_cache: dict = dict(DEFAULTS)


async def load_settings() -> None:
    global _cache
    doc = await db.settings.find_one({"_id": "global"})
    _cache = {**DEFAULTS, **((doc or {}).get("values") or {})}


def get(key: str):
    return _cache.get(key, DEFAULTS.get(key))


def all_values() -> dict:
    return dict(_cache)


async def set_value(key: str, value) -> None:
    _cache[key] = value
    await db.settings.update_one({"_id": "global"}, {"$set": {f"values.{key}": value}}, upsert=True)


async def toggle(key: str) -> bool:
    new_val = not bool(get(key))
    await set_value(key, new_val)
    return new_val


async def get_meta(key: str, default=None):
    """For small bits of non-toggle bookkeeping (e.g. 'last sent at'
    timestamps) that don't belong in the boolean `values` sub-doc."""
    doc = await db.settings.find_one({"_id": "global"}, {f"meta.{key}": 1})
    meta = (doc or {}).get("meta") or {}
    return meta.get(key, default)


async def set_meta(key: str, value) -> None:
    await db.settings.update_one({"_id": "global"}, {"$set": {f"meta.{key}": value}}, upsert=True)
