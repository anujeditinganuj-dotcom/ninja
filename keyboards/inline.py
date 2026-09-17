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
            make_button("💾 Backup", ButtonStyle.PRIMARY, callback_data="backup_export"),
            make_button("⚙️ Settings", ButtonStyle.PRIMARY, callback_data="settings_menu"),
        ],
        [make_button("❓ Help", ButtonStyle.PRIMARY, callback_data="help_menu")],
    ])


def my_bots_keyboard(bots: list) -> InlineKeyboardMarkup:
    """Renders like @BotFather's /mybots list: two bots per row, @username
    labels (colored, but not small-capped — small-caps would mangle handles)."""
    rows = []
    pair = []
    for b in bots:
        pair.append(InlineKeyboardButton(f"@{b['username']}", style=ButtonStyle.PRIMARY, callback_data=f"bot_select:{b['bot_id']}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([make_button("« Back", ButtonStyle.DANGER, callback_data="back_dashboard")])
    return InlineKeyboardMarkup(rows)


def bot_picker_keyboard(bots: list, callback_prefix: str) -> InlineKeyboardMarkup:
    """Generic bot-picker for standalone commands (/broadcast, /ban, /unban):
    same two-per-row @username layout as My Bots, but each button jumps
    straight into an existing per-bot flow via callback_prefix instead of
    opening the full bot panel."""
    rows = []
    pair = []
    for b in bots:
        pair.append(InlineKeyboardButton(f"@{b['username']}", style=ButtonStyle.PRIMARY, callback_data=f"{callback_prefix}:{b['bot_id']}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([make_button("« Back", ButtonStyle.DANGER, callback_data="back_dashboard")])
    return InlineKeyboardMarkup(rows)


def bot_panel_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("✏️ Edit Message", ButtonStyle.PRIMARY, callback_data=f"bot_message:{bot_id}")],
        [make_button("🖼 Edit Welcome Photo", ButtonStyle.PRIMARY, callback_data=f"bot_photo:{bot_id}")],
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


def message_type_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🎉 Normal Message", ButtonStyle.PRIMARY, callback_data=f"setmsg_normal:{bot_id}")],
        [make_button("🔧 Maintenance Message", ButtonStyle.PRIMARY, callback_data=f"setmsg_maint:{bot_id}")],
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


def force_sub_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🟢 Enable / Change Channel", ButtonStyle.SUCCESS, callback_data=f"fs_enable:{bot_id}")],
        [make_button("🔴 Disable", ButtonStyle.DANGER, callback_data=f"fs_disable:{bot_id}")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data=f"bot_select:{bot_id}")],
    ])


def ban_menu_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("🚫 Ban User", ButtonStyle.DANGER, callback_data=f"bot_ban_start:{bot_id}")],
        [make_button("✅ Unban User", ButtonStyle.SUCCESS, callback_data=f"bot_unban_start:{bot_id}")],
        [make_button("📋 Banned List", ButtonStyle.PRIMARY, callback_data=f"bot_ban_list:{bot_id}")],
        [make_button("« Back", ButtonStyle.DANGER, callback_data=f"bot_select:{bot_id}")],
    ])


def join_channel_keyboard(invite_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [make_button("📢 Join Channel", ButtonStyle.PRIMARY, url=invite_link)],
        [make_button("✅ I've Joined", ButtonStyle.SUCCESS, callback_data="fs_recheck")],
    ])


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
