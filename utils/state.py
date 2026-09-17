"""Simple in-memory conversation state machine for the owner's admin flows
(connect bot, set message, set button, etc). Only the OWNER_ID ever writes
to this, so a process-local dict is sufficient and avoids extra DB round trips.
"""
from typing import Optional

_user_states: dict[int, dict] = {}

# Every real bot command, master-bot-wide. Text-input flows (awaiting_broadcast,
# awaiting_ban_user_id, etc.) must exclude these, otherwise a command typed
# while a flow is active gets swallowed as if it were the flow's freeform
# data instead of running the command (see handlers using this below).
RESERVED_COMMANDS = [
    "start", "help", "bots", "mybots", "connect", "stats", "settings",
    "cancel", "restore", "broadcast", "ban", "unban",
]


def set_state(user_id: int, action: str, data: Optional[dict] = None) -> None:
    _user_states[user_id] = {"action": action, "data": data or {}}


def get_state(user_id: int) -> Optional[dict]:
    return _user_states.get(user_id)


def clear_state(user_id: int) -> None:
    _user_states.pop(user_id, None)
