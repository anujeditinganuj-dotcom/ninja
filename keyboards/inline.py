from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.textstyle import SC

try:
    from pyrogram.enums import ButtonStyle
    BUTTON_STYLE_SUPPORTED = True
except ImportError:
    BUTTON_STYLE_SUPPORTED = False


def make_button(text: str, callback_data: str = None, url: str = None,
                 style: "ButtonStyle" = None, smallcaps: bool = True) -> InlineKeyboardButton:
    """Small-caps the label (unless smallcaps=False — used for the owner's
    own custom end-user button text) and, when the installed pyrogram/
    kurigram build supports it, applies a Telegram-colored button style.
    Falls back to a plain button automatically on builds without style
    support, so this never breaks the bot."""
    kwargs = {"text": SC(text) if smallcaps else text}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    if BUTTON_STYLE_SUPPORTED and style is not None:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)


# Shorthand style constants (None on unsupported builds, so passing them
# into make_button() is always safe).
BTN_PRIMARY = ButtonStyle.PRIMARY if BUTTON_STYLE_SUPPORTED else None
BTN_DANGER = ButtonStyle.DANGER if BUTTON_STYLE_SUPPORTED else None


def dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("➕ Connect Bot", callback_data="connect_bot", style=BTN_PRIMARY)],
        [make_button("🤖 My Bots", callback_data="my_bots", style=BTN_PRIMARY)],
        [
            make_button("🛠 Maintenance", callback_data="bulk_maintenance_menu"),
            make_button("✏️ Custom Message", callback_data="message_menu"),
        ],
        [
            make_button("🔘 Buttons", callback_data="buttons_menu"),
            make_button("📊 Statistics", callback_data="stats_menu"),
        ],
        [
            make_button("💾 Backup", callback_data="backup_export"),
            make_button("⚙️ Settings", callback_data="settings_menu"),
        ],
        [make_button("❓ Help", callback_data="help_menu")],
    ])


def my_bots_keyboard(bots: list) -> InlineKeyboardMarkup:
    """Renders exactly like @BotFather's /mybots list: two bots per row,
    @username labels — colored + small-caps."""
    rows = []
    pair = []
    for b in bots:
        pair.append(make_button(f"@{b['username']}", callback_data=f"bot_select:{b['bot_id']}", style=BTN_PRIMARY))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([make_button("« Back", callback_data="back_dashboard")])
    return InlineKeyboardMarkup(rows)


def bot_panel_keyboard(bot_id: int, photo_spoiler: bool = False) -> InlineKeyboardMarkup:
    blur_label = "🌫️ Blur Photo: ON" if photo_spoiler else "🌫️ Blur Photo: OFF"
    return InlineKeyboardMarkup([
        [make_button("✏️ Edit Message", callback_data=f"bot_message:{bot_id}", style=BTN_PRIMARY)],
        [make_button("🖼 Edit Photo", callback_data=f"bot_photo:{bot_id}", style=BTN_PRIMARY)],
        [
            make_button("🙈 Blur Text", callback_data=f"bot_blur:{bot_id}"),
            make_button(blur_label, callback_data=f"bot_photospoiler:{bot_id}", style=BTN_PRIMARY if photo_spoiler else None),
        ],
        [
            make_button("🛠 Maintenance", callback_data=f"bot_maintenance:{bot_id}"),
            make_button("🔒 Force-Sub", callback_data=f"bot_forcesub:{bot_id}"),
        ],
        [
            make_button("🚫 Ban / Unban", callback_data=f"bot_ban_menu:{bot_id}", style=BTN_DANGER),
        ],
        [
            make_button("🔘 Buttons", callback_data=f"bot_buttons:{bot_id}"),
            make_button("📢 Broadcast", callback_data=f"bot_broadcast:{bot_id}"),
        ],
        [
            make_button("👀 Preview", callback_data=f"bot_preview:{bot_id}"),
            make_button("📊 Statistics", callback_data=f"bot_stats:{bot_id}"),
        ],
        [
            make_button("📥 Export Users", callback_data=f"bot_export:{bot_id}"),
            make_button("⚙️ Bot Settings", callback_data=f"bot_settings:{bot_id}"),
        ],
        [make_button("🗑 Disconnect", callback_data=f"bot_disconnect:{bot_id}", style=BTN_DANGER)],
        [make_button("« Back", callback_data="my_bots")],
    ])


def bot_picker_keyboard(bots: list, callback_prefix: str) -> InlineKeyboardMarkup:
    """Generic bot-picker for standalone flows (/broadcast, /ban, /unban,
    delete-bot): same two-per-row @username layout as My Bots, but each
    button jumps straight into an existing per-bot flow via
    callback_prefix instead of opening the full bot panel."""
    rows = []
    pair = []
    for b in bots:
        pair.append(make_button(f"@{b['username']}", callback_data=f"{callback_prefix}:{b['bot_id']}", style=BTN_PRIMARY))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([make_button("« Back", callback_data="back_dashboard", style=BTN_DANGER)])
    return InlineKeyboardMarkup(rows)


def photo_type_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🎉 Normal Message Photo", callback_data=f"setphoto_normal:{bot_id}", style=BTN_PRIMARY)],
        [make_button("🔧 Maintenance Message Photo", callback_data=f"setphoto_maint:{bot_id}", style=BTN_PRIMARY)],
        [make_button("« Back", callback_data=f"bot_select:{bot_id}")],
    ])


def ban_menu_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🚫 Ban User", callback_data=f"bot_ban_start:{bot_id}", style=BTN_DANGER)],
        [make_button("✅ Unban User", callback_data=f"bot_unban_start:{bot_id}", style=BTN_PRIMARY)],
        [make_button("📋 Banned List", callback_data=f"bot_ban_list:{bot_id}")],
        [make_button("« Back", callback_data=f"bot_select:{bot_id}")],
    ])


def confirm_keyboard(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            make_button("✅ Confirm", callback_data=confirm_cb, style=BTN_PRIMARY),
            make_button("❌ Cancel", callback_data=cancel_cb, style=BTN_DANGER),
        ]
    ])


def message_type_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🎉 Normal Message", callback_data=f"setmsg_normal:{bot_id}", style=BTN_PRIMARY)],
        [make_button("🔧 Maintenance Message", callback_data=f"setmsg_maint:{bot_id}", style=BTN_PRIMARY)],
        [make_button("« Back", callback_data=f"bot_select:{bot_id}")],
    ])


def maintenance_keyboard(bot_id: int, bot_doc: dict | None = None) -> InlineKeyboardMarkup:
    go_live = bool(bot_doc.get("go_live")) if bot_doc else False
    live_label = "🚀 Go Live: ON (tap to turn off)" if go_live else "🚀 Go Live (Full-time)"
    live_cb = f"golive_{'off' if go_live else 'on'}:{bot_id}"
    return InlineKeyboardMarkup([
        [
            make_button("🟢 Enable", callback_data=f"maint_on:{bot_id}", style=BTN_PRIMARY),
            make_button("🔴 Disable", callback_data=f"maint_off:{bot_id}", style=BTN_DANGER),
        ],
        [make_button(live_label, callback_data=live_cb, style=BTN_PRIMARY if go_live else None)],
        [make_button("« Back", callback_data=f"bot_select:{bot_id}")],
    ])


def bulk_maintenance_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🟢 Enable ALL", callback_data="bulk_maint_on", style=BTN_PRIMARY)],
        [make_button("🔴 Disable ALL", callback_data="bulk_maint_off", style=BTN_DANGER)],
        [make_button("🤖 Per-bot instead", callback_data="my_bots")],
        [make_button("« Back", callback_data="back_dashboard")],
    ])


def force_sub_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🟢 Enable / Change Channel", callback_data=f"fs_enable:{bot_id}", style=BTN_PRIMARY)],
        [make_button("🔴 Disable", callback_data=f"fs_disable:{bot_id}", style=BTN_DANGER)],
        [make_button("« Back", callback_data=f"bot_select:{bot_id}")],
    ])


def force_sub_menu_keyboard(bot_id: int, channels: list, enabled: bool) -> InlineKeyboardMarkup:
    """channels: normalized list from utils.force_sub.normalize_force_sub,
    each {"channel", "invite_link", "title"}. Tapping a channel removes it
    (fs_remove:{bot_id}:{index}); toggle/add apply to the whole list."""
    from utils.force_sub import channel_label

    rows = [
        [make_button(f"🗑 {channel_label(c)}", callback_data=f"fs_remove:{bot_id}:{i}")]
        for i, c in enumerate(channels)
    ]
    rows.append([make_button("➕ Add Channel", callback_data=f"fs_add:{bot_id}", style=BTN_PRIMARY)])
    toggle_label = "🔴 Disable" if enabled else "🟢 Enable"
    rows.append([make_button(toggle_label, callback_data=f"fs_toggle:{bot_id}", style=BTN_DANGER if enabled else BTN_PRIMARY)])
    rows.append([make_button("« Back", callback_data=f"bot_select:{bot_id}")])
    return InlineKeyboardMarkup(rows)


def join_channel_keyboard(invite_link: str) -> InlineKeyboardMarkup:
    # Left un-styled/un-smallcapped on purpose: this one's shown to the
    # managed bot's *end users*, not the owner's control panel.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=invite_link)],
        [InlineKeyboardButton("✅ I've Joined", callback_data="fs_recheck")],
    ])


# --- Custom button styling: emoji wrap + color, picked when a button is
# added, stored per-button in the DB, applied automatically at render time.

BUTTON_EMOJI_PRESETS = {
    "none": ("", "", "⬜ No emoji"),
    "butterfly": ("✨🦋", "🦋✨", "✨🦋 Butterfly"),
    "money": ("💸", "💸", "💸 Money"),
    "heart": ("💗", "💗", "💗 Heart"),
    "fire": ("🔥", "🔥", "🔥 Fire"),
    "star": ("⭐", "⭐", "⭐ Star"),
    "announce": ("📢", "", "📢 Announce"),
}

BUTTON_COLOR_STYLES = {
    "default": (None, "⚪ Default"),
    "blue": (BTN_PRIMARY, "🔵 Blue"),
    "red": (BTN_DANGER, "🔴 Red"),
}


def button_emoji_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"btnemoji:{key}")]
            for key, (_, _, label) in BUTTON_EMOJI_PRESETS.items()]
    rows.append([InlineKeyboardButton("Cancel", callback_data="btnstyle_cancel")])
    return InlineKeyboardMarkup(rows)


def button_color_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"btncolor:{key}")]
            for key, (_, label) in BUTTON_COLOR_STYLES.items()]
    rows.append([InlineKeyboardButton("Cancel", callback_data="btnstyle_cancel")])
    return InlineKeyboardMarkup(rows)


def build_user_buttons(buttons: list):
    """buttons: list of rows, each row a list of
    {"text", "url", "emoji_prefix", "emoji_suffix", "color"}.
    These are the owner's own custom buttons for their managed bot's end
    users — the label text itself is left exactly as typed (not
    small-capped); only the chosen emoji wrap + color style are applied."""
    if not buttons:
        return None
    rows = []
    for row in buttons:
        if not row:
            continue
        btn_row = []
        for b in row:
            label = f"{b.get('emoji_prefix', '')}{b['text']}{b.get('emoji_suffix', '')}"
            style, _ = BUTTON_COLOR_STYLES.get(b.get("color"), (None, None))
            btn_row.append(make_button(label, url=b["url"], style=style, smallcaps=False))
        if btn_row:
            rows.append(btn_row)
    if not rows:
        return None
    return InlineKeyboardMarkup(rows)


def back_keyboard(cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[make_button("« Back", callback_data=cb)]])


# --- Settings ---------------------------------------------------------

def settings_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("👤 Admin", callback_data="settings_admin", style=BTN_PRIMARY)],
        [make_button("🤖 Bot Management", callback_data="settings_botmgmt", style=BTN_PRIMARY)],
        [make_button("🔔 Notifications", callback_data="settings_notifications", style=BTN_PRIMARY)],
        [make_button("🔐 Security", callback_data="settings_security", style=BTN_PRIMARY)],
        [make_button("🗄️ Database", callback_data="settings_database", style=BTN_PRIMARY)],
        [
            make_button("📊 System Status", callback_data="settings_system_status"),
            make_button("ℹ️ About", callback_data="settings_about"),
        ],
        [make_button("« Back", callback_data="back_dashboard")],
    ])


def settings_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🔐 Admin Access", callback_data="admin_access_menu", style=BTN_PRIMARY)],
        [make_button("« Back", callback_data="settings_menu")],
    ])


def admin_access_keyboard(added_admins: list) -> InlineKeyboardMarkup:
    rows = [
        [make_button(f"🗑 {uid}", callback_data=f"admin_remove:{uid}", style=BTN_DANGER)]
        for uid in added_admins
    ]
    rows.append([make_button("➕ Add Admin", callback_data="admin_add", style=BTN_PRIMARY)])
    rows.append([make_button("« Back", callback_data="settings_admin")])
    return InlineKeyboardMarkup(rows)


def _toggle_row(label: str, key: str, values: dict) -> list:
    on = bool(values.get(key))
    return [make_button(f"{label}: {'🟢 ON' if on else '🔴 OFF'}", callback_data=f"setting_toggle:{key}",
                         style=BTN_PRIMARY if on else None)]


def settings_botmgmt_keyboard(values: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _toggle_row("🔄 Auto Reconnect", "auto_reconnect", values),
        _toggle_row("🚀 Auto Start Bots", "auto_start_bots", values),
        _toggle_row("🟢 Default: Maintenance", "default_maintenance_on_connect", values),
        [make_button("« Back", callback_data="settings_menu")],
    ])


def settings_notifications_keyboard(values: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _toggle_row("⚠️ Error Alerts", "notify_errors", values),
        _toggle_row("🔴 Bot Offline Alerts", "notify_offline", values),
        _toggle_row("📊 Daily Statistics", "notify_daily_stats", values),
        [make_button("« Back", callback_data="settings_menu")],
    ])


def settings_security_keyboard(values: dict, encryption_enabled: bool) -> InlineKeyboardMarkup:
    token_label = "🔑 Token Protection: 🟢 ON" if encryption_enabled else "🔑 Token Protection: 🔴 OFF"
    return InlineKeyboardMarkup([
        [make_button(token_label, callback_data="setting_info_token")],
        _toggle_row("🛡️ Access Control", "restrict_destructive_to_owner", values),
        [make_button("📋 Activity Logs", callback_data="settings_activity_logs")],
        [make_button("« Back", callback_data="settings_menu")],
    ])


def settings_database_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("📊 Connection Status", callback_data="settings_db_status", style=BTN_PRIMARY)],
        [make_button("💾 Data Information", callback_data="settings_db_info", style=BTN_PRIMARY)],
        [make_button("« Back", callback_data="settings_menu")],
    ])
