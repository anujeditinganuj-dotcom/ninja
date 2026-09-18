from database import db
from config import OWNER_ID

# Every is_owner()-style check across the 12 handler files is a plain sync
# function called dozens of times per conversation (including inside
# filters.create lambdas, which can't await). Rather than make all of those
# call sites async just to check a DB-backed admin list, we keep one
# in-memory cache here — loaded once at startup and refreshed on every
# add/remove — so is_admin() stays a simple, instant set-membership check.
_admin_ids: set[int] = {OWNER_ID}


async def load_admins() -> None:
    """Call once at startup (and it's also refreshed internally on every
    add_admin/remove_admin), so the cache never actually goes stale."""
    global _admin_ids
    ids = {doc["user_id"] async for doc in db.admins.find({}, {"user_id": 1})}
    _admin_ids = {OWNER_ID} | ids


def is_admin(user_id: int) -> bool:
    """True for the real OWNER_ID or anyone added via Settings → Admin Access."""
    return user_id in _admin_ids


def is_owner_id(user_id: int) -> bool:
    """True only for the real OWNER_ID from config — never an added admin.
    Used to gate the handful of actions too dangerous to delegate."""
    return user_id == OWNER_ID


def list_admins() -> list[int]:
    return sorted(_admin_ids)


def list_added_admins() -> list[int]:
    """Admins added via the panel, excluding the real owner."""
    return sorted(_admin_ids - {OWNER_ID})


async def add_admin(user_id: int) -> bool:
    if user_id in _admin_ids:
        return False
    await db.admins.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)
    _admin_ids.add(user_id)
    return True


async def remove_admin(user_id: int) -> bool:
    if user_id == OWNER_ID or user_id not in _admin_ids:
        return False
    await db.admins.delete_one({"user_id": user_id})
    _admin_ids.discard(user_id)
    return True


def can_do_destructive(user_id: int) -> bool:
    """Gate for actions too risky to delegate by default: disconnecting a
    bot, restoring a backup, managing the admin list itself. The real owner
    can always do these; an added admin can too only if the owner has
    turned OFF Settings → Security → Access Control (restrict-to-owner)."""
    if user_id == OWNER_ID:
        return True
    if user_id not in _admin_ids:
        return False
    from services.settings_service import get
    return not get("restrict_destructive_to_owner")
