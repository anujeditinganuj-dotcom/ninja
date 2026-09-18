try:
    from pyrogram.enums import ButtonStyle
    _BUTTON_STYLE_SUPPORTED = True
except ImportError:
    # Installed kurigram/pyrogram build predates the colored-button enum
    # (Bot API 9.4+ feature). Rather than crash the whole app at import
    # time over button color, degrade to plain (uncolored) buttons.
    class _NoButtonStyle:
        DEFAULT = PRIMARY = DANGER = SUCCESS = None
    ButtonStyle = _NoButtonStyle()
    _BUTTON_STYLE_SUPPORTED = False

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.force_sub import channel_label
from utils.textstyle import SC


# ── colored button helper ────────────────────────────────────────────────
# Every button in this file now gets an explicit color — default is PRIMARY
# (blue) so nothing renders as the plain/transparent Bot-API style.
def make_button(text: str, style: ButtonStyle = ButtonStyle.PRIMARY, small_caps: bool = True, **kwargs) -> InlineKeyboardButton:
    """Builds an InlineKeyboardButton with small-caps label (default on) and
    a Bot-API button color (PRIMARY/DANGER/SUCCESS) where the installed
    pyrogram/kurigram build supports it; plain buttons otherwise.
    kwargs: callback_data / url / etc., same as InlineKeyboardButton."""
    label = SC(text) if small_caps else text
    if _BUTTON_STYLE_SUPPORTED:
        return InlineKeyboardButton(label, style=style, **kwargs)
    return InlineKeyboardButton(label, **kwargs)


def dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("➕ Connect Bot", ButtonStyle.PRIMARY, callback_data="connect_bot")],
        [make_button("🤖 My Bots", ButtonStyle.PRIMARY, callback_data="my_bots")],
        [
            make_button("🛠 Maintenance", ButtonStyle.PRIMARY, callback_data="bulk_maintenance_menu"),
            make_button("✏️ Custom Message", ButtonStyle.PRIMARY, callback_data="message_menu"),
        ],
        [
            make_button("🔘 Buttons", ButtonStyle.PRIMARY, callback_data="buttons_menu"),
            make_button("📊 Statistics", ButtonStyle.PRIMARY, callback_data="stats_menu"),
        ],
        [
            make_button("📢 Broadcast", ButtonStyle.PRIMARY, callback_data="broadcast_menu"),
            make_button("💾 Backup", ButtonStyle.PRIMARY, callback_data="backup_export"),
        ],
        [make_button("⚙️ Settings", ButtonStyle.PRIMARY, callback_data="settings_menu")],
        [make_button("❓ Help", ButtonStyle.PRIMARY, callback_data="help_menu")],
    ])


def my_bots_keyboard(bots: list) -> InlineKeyboardMarkup:
    """One bot per row (matches @BotFather's own /mybots layout) — tap a
    bot's @username to open its full panel. Add/Delete sit together below
    the list: Add jumps straight into the connect flow, Delete opens a
    picker (bot_picker_keyboard) so you choose which bot before the same
    disconnect-confirm flow used elsewhere runs."""
    rows = [
        [InlineKeyboardButton(f"@{b['username']}", style=ButtonStyle.PRIMARY, callback_data=f"bot_select:{b['bot_id']}")]
        for b in bots
    ]
    rows.append([
        make_button("➕ Add Bot", ButtonStyle.SUCCESS, callback_data="connect_bot"),
        make_button("🗑 Delete Bot", ButtonStyle.DANGER, callback_data="delete_bot_menu"),
    ])
    rows.append([make_button("« Back", ButtonStyle.DANGER, callback_data="back_dashboard")])
    return InlineKeyboardMarkup(rows)


def bot_picker_keyboard(bots: list, callback_prefix: str) -> InlineKeyboardMarkup:
    """Generic bot-picker for standalone commands (/broadcast, /ban, /unban):
    same one-per-row @username layout as My Bots (see the fix note there),
    but each button jumps straight into an existing per-bot flow via
    callback_prefix instead of opening the full bot panel."""
    rows = [
        [InlineKeyboardButton(f"@{b['username']}", style=ButtonStyle.PRIMARY, callback_data=f"{callback_prefix}:{b['bot_id']}")]
        for b in bots
    ]
    rows.append([make_button("« Back", ButtonStyle.DANGER, callback_data="back_dashboard")])
    return InlineKeyboardMarkup(rows)


def bot_panel_keyboard(bot_id: int, photo_spoiler: bool = False) -> InlineKeyboardMarkup:
    spoiler_label = "🌫️ Blur Photo: ON" if photo_spoiler else "🌫️ Blur Photo: OFF"
    return InlineKeyboardMarkup([
        [make_button("✏️ Edit Message", ButtonStyle.PRIMARY, callback_data=f"bot_message:{bot_id}")],
        [
            make_button("🖼 Edit Photo", ButtonStyle.PRIMARY, callback_data=f"bot_photo:{bot_id}"),
            make_button("🙈 Blur Text", ButtonStyle.PRIMARY, callback_data=f"bot_blur:{bot_id}"),
        ],
        [make_button(spoiler_label, ButtonStyle.SUCCESS if photo_spoiler else ButtonStyle.DANGER, callback_data=f"bot_photospoiler:{bot_id}")],
        [
            make_button("🛠 Maintenance", ButtonStyle.PRIMARY, callback_data=f"bot_maintenance:{bot_id}"),
            make_button("🔒 Force-Sub", ButtonStyle.PRIMARY, callback_data=f"bot_forcesub:{bot_id}"),
        ],
        [make_button("🚫 Ban / Unban", ButtonStyle.DANGER, callback_data=f"bot_ban_menu:{bot_id}")],
        [
            make_button("🔘 Buttons", ButtonStyle.PRIMARY, callback_data=f"bot_buttons:{bot_id}"),
            make_button("📢 Broadcast", ButtonStyle.PRIMARY, callback_data=f"bot_broadcast:{bot_id}"),
        ],
        [
            make_button("👀 Preview", ButtonStyle.PRIMARY, callback_data=f"bot_preview:{bot_id}"),
            make_button("📊 Statistics", ButtonStyle.PRIMARY, callback_data=f"bot_stats:{bot_id}"),
        ],
        [
            make_button("📥 Export Users", ButtonStyle.PRIMARY, callback_data=f"bot_export:{bot_id}"),
            make_button("⚙️ Bot Settings", ButtonStyle.PRIMARY, callback_data=f"bot_settings:{bot_id}"),
        ],
        [make_button("🗑 Disconnect", ButtonStyle.DANGER, callback_data=f"bot_disconnect:{bot_id}")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data="my_bots")],
    ])


def confirm_keyboard(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            make_button("✅ Confirm", ButtonStyle.SUCCESS, callback_data=confirm_cb),
            make_button("❌ Cancel", ButtonStyle.DANGER, callback_data=cancel_cb),
        ]
    ])


def buttons_menu_keyboard(bot_id: int, buttons: list) -> InlineKeyboardMarkup:
    rows = []
    for r, row in enumerate(buttons or []):
        for c, b in enumerate(row):
            rows.append([make_button(f"❌ {b['text']}", ButtonStyle.DANGER, callback_data=f"delbtn:{bot_id}:{r}:{c}")])
    rows.append([make_button("✨🦋 Add Button 🦋✨", ButtonStyle.SUCCESS, callback_data=f"addbtn:{bot_id}")])
    if buttons:
        rows.append([make_button("🗑 Clear All", ButtonStyle.DANGER, callback_data=f"clearbtns:{bot_id}")])
    rows.append([make_button("« Back", ButtonStyle.DANGER, callback_data=f"bot_select:{bot_id}")])
    return InlineKeyboardMarkup(rows)


def message_type_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🎉 Normal Message", ButtonStyle.PRIMARY, callback_data=f"setmsg_normal:{bot_id}")],
        [make_button("🔧 Maintenance Message", ButtonStyle.PRIMARY, callback_data=f"setmsg_maint:{bot_id}")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data=f"bot_select:{bot_id}")],
    ])


def photo_type_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🎉 Normal Welcome Photo", ButtonStyle.PRIMARY, callback_data=f"setphoto_normal:{bot_id}")],
        [make_button("🔧 Maintenance Photo", ButtonStyle.PRIMARY, callback_data=f"setphoto_maint:{bot_id}")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data=f"bot_select:{bot_id}")],
    ])


def maintenance_keyboard(bot_id: int, bot_doc: dict | None = None) -> InlineKeyboardMarkup:
    go_live = bool(bot_doc.get("go_live")) if bot_doc else False
    live_label = "🚀 Go Live: ON (tap to turn off)" if go_live else "🚀 Go Live (Full-time)"
    live_cb = f"golive_{'off' if go_live else 'on'}:{bot_id}"
    return InlineKeyboardMarkup([
        [
            make_button("🟢 Enable", ButtonStyle.SUCCESS, callback_data=f"maint_on:{bot_id}"),
            make_button("🔴 Disable", ButtonStyle.DANGER, callback_data=f"maint_off:{bot_id}"),
        ],
        [make_button(live_label, ButtonStyle.SUCCESS if go_live else ButtonStyle.PRIMARY, callback_data=live_cb)],
        [make_button("« Back", ButtonStyle.DANGER, callback_data=f"bot_select:{bot_id}")],
    ])


def bulk_maintenance_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🟢 Enable ALL", ButtonStyle.SUCCESS, callback_data="bulk_maint_on")],
        [make_button("🔴 Disable ALL", ButtonStyle.DANGER, callback_data="bulk_maint_off")],
        [make_button("🤖 Per-bot instead", ButtonStyle.PRIMARY, callback_data="my_bots")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data="back_dashboard")],
    ])


def force_sub_menu_keyboard(bot_id: int, channels: list, enabled: bool) -> InlineKeyboardMarkup:
    """channels: list of {"channel", "invite_link", "title"} dicts (see utils/force_sub.py).
    Each channel gets its own row with a tap-to-remove button; toggle only
    shows once there's at least one channel to toggle."""
    rows = [[make_button("➕ Add Channel", ButtonStyle.SUCCESS, callback_data=f"fs_add:{bot_id}")]]
    for index, entry in enumerate(channels):
        label = f"🗑 {channel_label(entry)}"
        rows.append([InlineKeyboardButton(label, style=ButtonStyle.DANGER, callback_data=f"fs_remove:{bot_id}:{index}")])
    if channels:
        toggle_label = "🔴 Disable" if enabled else "🟢 Enable"
        toggle_style = ButtonStyle.DANGER if enabled else ButtonStyle.SUCCESS
        rows.append([make_button(toggle_label, toggle_style, callback_data=f"fs_toggle:{bot_id}")])
    rows.append([make_button("« Back", ButtonStyle.DANGER, callback_data=f"bot_select:{bot_id}")])
    return InlineKeyboardMarkup(rows)


def ban_menu_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🚫 Ban User", ButtonStyle.DANGER, callback_data=f"bot_ban_start:{bot_id}")],
        [make_button("✅ Unban User", ButtonStyle.SUCCESS, callback_data=f"bot_unban_start:{bot_id}")],
        [make_button("📋 Banned List", ButtonStyle.PRIMARY, callback_data=f"bot_ban_list:{bot_id}")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data=f"bot_select:{bot_id}")],
    ])


def join_channel_keyboard(channels: list) -> InlineKeyboardMarkup:
    """channels: list of (label, invite_link) tuples — one row per unjoined channel,
    plus a single recheck button at the bottom for all of them."""
    rows = [[InlineKeyboardButton(f"📢 {label}", style=ButtonStyle.PRIMARY, url=url)] for label, url in channels]
    rows.append([make_button("✅ I've Joined", ButtonStyle.SUCCESS, callback_data="fs_recheck")])
    return InlineKeyboardMarkup(rows)


def build_user_buttons(buttons: list):
    """buttons: list of rows, each row a list of {"text": str, "url": str}.
    These are labels the bot owner typed themselves for their own bot's
    /start message — colored (PRIMARY) but not small-capped, so their exact
    wording is preserved."""
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(b["text"], style=ButtonStyle.PRIMARY, url=b["url"]) for b in row] for row in buttons if row]
    if not rows:
        return None
    return InlineKeyboardMarkup(rows)


def back_keyboard(cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[make_button("« Back", ButtonStyle.DANGER, callback_data=cb)]])


# ── Settings menu ────────────────────────────────────────────────────────
# These were referenced by handlers/settings.py but never actually defined
# here, so importing that module raised ImportError — which is why it was
# never registered in main.py, and the panel fell back to a bare "Open a
# bot from My Bots..." placeholder stub in handlers/admin.py instead of
# this real menu tree.
def settings_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("👤 Admin Management", ButtonStyle.PRIMARY, callback_data="settings_admin")],
        [make_button("🤖 Bot Management", ButtonStyle.PRIMARY, callback_data="settings_botmgmt")],
        [make_button("🔔 Notifications", ButtonStyle.PRIMARY, callback_data="settings_notifications")],
        [make_button("🔐 Security", ButtonStyle.PRIMARY, callback_data="settings_security")],
        [make_button("🗄️ Database", ButtonStyle.PRIMARY, callback_data="settings_database")],
        [make_button("📊 System Status", ButtonStyle.PRIMARY, callback_data="settings_system_status")],
        [make_button("📝 Activity Logs", ButtonStyle.PRIMARY, callback_data="settings_activity_logs")],
        [make_button("ℹ️ About", ButtonStyle.PRIMARY, callback_data="settings_about")],
        [make_button("🔄 Refresh", ButtonStyle.PRIMARY, callback_data="settings_menu")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data="back_dashboard")],
    ])


def settings_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🔐 Manage Admin Access", ButtonStyle.PRIMARY, callback_data="admin_access_menu")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data="settings_menu")],
    ])


def admin_access_keyboard(added_admin_ids: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"➖ Remove {uid}", style=ButtonStyle.DANGER, callback_data=f"admin_remove:{uid}")]
        for uid in added_admin_ids
    ]
    rows.append([make_button("➕ Add Admin", ButtonStyle.SUCCESS, callback_data="admin_add")])
    rows.append([make_button("« Back", ButtonStyle.DANGER, callback_data="settings_admin")])
    return InlineKeyboardMarkup(rows)


def _toggle_row(label: str, key: str, values: dict) -> list:
    on = bool(values.get(key))
    return [make_button(
        f"{'🟢' if on else '🔴'} {label}: {'ON' if on else 'OFF'}",
        ButtonStyle.SUCCESS if on else ButtonStyle.DANGER,
        callback_data=f"setting_toggle:{key}",
    )]


def settings_botmgmt_keyboard(values: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _toggle_row("Auto Reconnect", "auto_reconnect", values),
        _toggle_row("Auto Start Bots", "auto_start_bots", values),
        _toggle_row("Default: Maintenance", "default_maintenance_on_connect", values),
        [make_button("« Back", ButtonStyle.DANGER, callback_data="settings_menu")],
    ])


def settings_notifications_keyboard(values: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _toggle_row("Error Alerts", "notify_errors", values),
        _toggle_row("Bot Offline Alerts", "notify_offline", values),
        _toggle_row("Daily Statistics", "notify_daily_stats", values),
        [make_button("« Back", ButtonStyle.DANGER, callback_data="settings_menu")],
    ])


def settings_security_keyboard(values: dict, encryption_enabled: bool) -> InlineKeyboardMarkup:
    token_label = "🟢 Token Protection: ON" if encryption_enabled else "🔴 Token Protection: OFF"
    return InlineKeyboardMarkup([
        [make_button(token_label, ButtonStyle.SUCCESS if encryption_enabled else ButtonStyle.DANGER,
                     callback_data="setting_info_token")],
        _toggle_row("Access Control", "restrict_destructive_to_owner", values),
        [make_button("📋 Activity Logs", ButtonStyle.PRIMARY, callback_data="settings_activity_logs")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data="settings_menu")],
    ])


def settings_database_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("📊 Status", ButtonStyle.PRIMARY, callback_data="settings_db_status")],
        [make_button("💾 Data Info", ButtonStyle.PRIMARY, callback_data="settings_db_info")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data="settings_menu")],
    ])
