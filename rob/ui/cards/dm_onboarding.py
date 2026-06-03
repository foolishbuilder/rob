"""Components V2 cards for the DM-based Dom/me onboarding flow.

All cards here are test-guild-only. The cards themselves are dumb renderers
— gating to ``is_test_guild`` is the caller's responsibility. The interaction
handlers live in :mod:`rob.discord.cogs.dm_onboarding` and the orchestration
in :mod:`rob.services.dm_onboarding_service`.

Each card returns a :class:`~rob.ui.render.RenderedMessage` whose
``view`` is a :class:`~discord.ui.LayoutView`. Callers ``message.edit(**rendered.edit_kwargs())``
to update the same DM message as the flow progresses.

The wording used here is the *exact* onboarding copy from the spec; do not
edit it without coordinating with the spec.
"""

from __future__ import annotations

import discord

from rob.ui.render import RenderedMessage, add_card_actions
from rob.ui.theme import COLOR_INFO, COLOR_SUCCESS, COLOR_WARNING


# ---------------------------------------------------------------------------
# Custom IDs - kept stable so persistent views can be re-bound after restart.
# ---------------------------------------------------------------------------
ONBOARDING_PREFIX = "rob:dm_onboarding:"
ID_INTRO_OPEN_MODAL = f"{ONBOARDING_PREFIX}intro:open_modal"
ID_INTRO_MODAL = f"{ONBOARDING_PREFIX}intro:modal"
ID_INTRO_MODAL_FIELD = f"{ONBOARDING_PREFIX}intro:modal:throne_input"
ID_IDENTITY_YES = f"{ONBOARDING_PREFIX}identity:yes"
ID_IDENTITY_NO = f"{ONBOARDING_PREFIX}identity:no"
ID_WEBHOOK_RETRY = f"{ONBOARDING_PREFIX}webhook:retry"
ID_PREFS_NOTIFICATIONS = f"{ONBOARDING_PREFIX}prefs:notifications"
ID_PREFS_LEADERBOARD = f"{ONBOARDING_PREFIX}prefs:leaderboard"
ID_PREFS_SAVE = f"{ONBOARDING_PREFIX}prefs:save"

MIGRATION_PREFIX = "rob:dm_migration:"
ID_MIGRATION_OPEN_PREFS = f"{MIGRATION_PREFIX}open_prefs"
ID_MIGRATION_DEFER = f"{MIGRATION_PREFIX}defer_7d"
ID_MIGRATION_NOTIFICATIONS = f"{MIGRATION_PREFIX}notifications"
ID_MIGRATION_LEADERBOARD = f"{MIGRATION_PREFIX}leaderboard"
ID_MIGRATION_SAVE = f"{MIGRATION_PREFIX}save"

# Preference option values stored on the SelectOption.
NOTIFY_ON_VALUE = "notify_on"
NOTIFY_OFF_VALUE = "notify_off"
LEADERBOARD_SHOW_VALUE = "leaderboard_show"
LEADERBOARD_HIDE_VALUE = "leaderboard_hide"

_DIVIDER = "——————————————"


def _layout(accent_color: discord.Colour | None = None) -> discord.ui.LayoutView:
    return discord.ui.LayoutView(timeout=None)


def _container(accent_color: discord.Colour | None = None) -> "discord.ui.Container":
    return discord.ui.Container(accent_color=accent_color)


# ---------------------------------------------------------------------------
# Step 1 — Intro DM card
# ---------------------------------------------------------------------------


def intro_card(name: str | None = None) -> RenderedMessage:
    """Step 1: greet the Dom/me and ask for their Throne username or link."""

    display = (name or "there").strip() or "there"
    view = _layout()
    container = _container(accent_color=COLOR_INFO)
    container.add_item(discord.ui.TextDisplay(f"## Hey {display}, Rob here!"))
    container.add_item(
        discord.ui.TextDisplay(
            "Thanks for wanting to sign up to Throne tracking. Before we can "
            "start tracking your notifications, we need to do some initial "
            "setup first."
        )
    )
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(_DIVIDER))
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.TextDisplay(
            "Firstly, what was your Throne username or link?"
        )
    )
    view.add_item(container)

    button = discord.ui.Button(
        style=discord.ButtonStyle.primary,
        label="Enter Throne details",
        custom_id=ID_INTRO_OPEN_MODAL,
    )
    add_card_actions(view, button)
    return RenderedMessage(view=view)


def build_intro_modal() -> discord.ui.Modal:
    """Modal that captures the Throne username or link."""

    class _ThroneInputModal(discord.ui.Modal, title="Your Throne profile"):
        throne_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Throne username or link",
            placeholder="e.g. yourname  or  https://throne.com/yourname",
            required=True,
            max_length=200,
            custom_id=ID_INTRO_MODAL_FIELD,
        )

        def __init__(self) -> None:
            super().__init__(custom_id=ID_INTRO_MODAL)

    return _ThroneInputModal()


# ---------------------------------------------------------------------------
# Step 3 — Identity confirmation card
# ---------------------------------------------------------------------------


def identity_confirm_card(
    *,
    throne_handle: str,
    throne_display_name: str | None,
) -> RenderedMessage:
    """Step 3: confirm the Throne identity Rob resolved."""

    display = (throne_display_name or throne_handle or "").strip() or throne_handle
    view = _layout()
    container = _container(accent_color=COLOR_INFO)
    container.add_item(
        discord.ui.TextDisplay(
            "Thanks! Just to make sure I’ve got the right details does this look right?"
        )
    )
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(_DIVIDER))
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.TextDisplay(f"**Throne Username:** {throne_handle}")
    )
    container.add_item(
        discord.ui.TextDisplay(f"**Name as appears on Throne:** {display}")
    )
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(_DIVIDER))
    view.add_item(container)

    yes = discord.ui.Button(
        style=discord.ButtonStyle.success,
        label="Sure does!",
        custom_id=ID_IDENTITY_YES,
    )
    no = discord.ui.Button(
        style=discord.ButtonStyle.danger,
        label="Not quite!",
        custom_id=ID_IDENTITY_NO,
    )
    add_card_actions(view, yes, no)
    return RenderedMessage(view=view)


# ---------------------------------------------------------------------------
# Step 4 — Webhook setup / waiting card
# ---------------------------------------------------------------------------


def webhook_setup_card(*, webhook_url: str) -> RenderedMessage:
    """Step 4: instruct the Dom/me to install Rob's webhook URL into Throne
    and send a Test Webhook. Rob waits on this same message and auto-edits
    when the test arrives."""

    view = _layout()
    container = _container(accent_color=COLOR_WARNING)
    container.add_item(
        discord.ui.TextDisplay(
            "## Awesome, now here comes the bit with the most steps."
        )
    )
    container.add_item(
        discord.ui.TextDisplay(
            "To help Rob get your sends the second they are sent, we need to "
            "setup “Webhooks” inside of Throne. Here’s how:"
        )
    )
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.TextDisplay(
            "**1.** Open Throne\n"
            "**2.** Go to your webhook settings / integrations area\n"
            "**3.** Add Rob’s webhook URL (below)\n"
            "**4.** Save the settings\n"
            "**5.** Click Test Webhook in Throne"
        )
    )
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("**Rob’s webhook URL:**"))
    container.add_item(discord.ui.TextDisplay(f"```\n{webhook_url}\n```"))
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.TextDisplay(
            "Once you’ve clicked “Test Webhook” come back here to see if Rob "
            "picked up your Test Send!"
        )
    )
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("**Status:** Nothing from Throne just yet…"))
    view.add_item(container)

    retry = discord.ui.Button(
        style=discord.ButtonStyle.secondary,
        label="Doesn’t look to have worked!",
        custom_id=ID_WEBHOOK_RETRY,
    )
    add_card_actions(view, retry)
    return RenderedMessage(view=view)


# Backwards-compat shim used by older tests.
def webhook_waiting_card() -> RenderedMessage:
    """Lightweight refresh of the webhook card without a known URL."""

    return webhook_setup_card(webhook_url="(your webhook URL above)")


# ---------------------------------------------------------------------------
# Step 6 — Preferences selection card
# ---------------------------------------------------------------------------


class PreferencesView(discord.ui.LayoutView):
    """Stage 6: notification + leaderboard preferences via Components V2.

    Each preference is a :class:`~discord.ui.Select` inside the same
    :class:`~discord.ui.Container`, with a Save button to commit. The cog
    reads the current selections off this view when Save fires.
    """

    def __init__(
        self,
        *,
        default_notifications_enabled: bool = True,
        default_leaderboard_visible: bool = True,
        notifications_custom_id: str = ID_PREFS_NOTIFICATIONS,
        leaderboard_custom_id: str = ID_PREFS_LEADERBOARD,
        save_custom_id: str = ID_PREFS_SAVE,
        intro_lines: tuple[str, ...] = (
            "## And just like that, the hard bit is done.",
            "Now just tell Rob how you want things handled from here.",
        ),
    ) -> None:
        super().__init__(timeout=None)

        container = discord.ui.Container(accent_color=COLOR_INFO)
        for line in intro_lines:
            container.add_item(discord.ui.TextDisplay(line))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(_DIVIDER))
        container.add_item(discord.ui.Separator())

        # ---- Section 1: Notifications ----
        container.add_item(discord.ui.TextDisplay("### 📬 Send notifications"))
        container.add_item(
            discord.ui.TextDisplay(
                "How should Rob notify you when a send comes in?"
            )
        )
        self.notifications_select = discord.ui.Select(
            custom_id=notifications_custom_id,
            placeholder="📬 Send notifications",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="📬 DM me when a send comes in",
                    value=NOTIFY_ON_VALUE,
                    default=default_notifications_enabled,
                ),
                discord.SelectOption(
                    label="🔕 Do not DM me about sends",
                    value=NOTIFY_OFF_VALUE,
                    default=not default_notifications_enabled,
                ),
            ],
        )
        container.add_item(self.notifications_select)
        container.add_item(discord.ui.Separator())

        # ---- Section 2: Leaderboard ----
        container.add_item(discord.ui.TextDisplay("### 📊 Leaderboard visibility"))
        container.add_item(
            discord.ui.TextDisplay(
                "Should Rob show you on the server leaderboard?"
            )
        )
        self.leaderboard_select = discord.ui.Select(
            custom_id=leaderboard_custom_id,
            placeholder="📊 Leaderboard visibility",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="👑 Show me on the leaderboard",
                    value=LEADERBOARD_SHOW_VALUE,
                    default=default_leaderboard_visible,
                ),
                discord.SelectOption(
                    label="🔒 Keep me off the leaderboard",
                    value=LEADERBOARD_HIDE_VALUE,
                    default=not default_leaderboard_visible,
                ),
            ],
        )
        container.add_item(self.leaderboard_select)
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.TextDisplay(
                "-# You can always change these settings later with `/settings` "
                "in your DMs or in the server."
            )
        )
        container.add_item(discord.ui.Separator())

        save = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Save preferences",
            custom_id=save_custom_id,
        )
        self.save_button = save
        container.add_item(discord.ui.ActionRow(save))
        self.add_item(container)

    @property
    def chosen_notifications_enabled(self) -> bool:
        values = self.notifications_select.values
        if not values:
            return True
        return values[0] == NOTIFY_ON_VALUE

    @property
    def chosen_leaderboard_visible(self) -> bool:
        values = self.leaderboard_select.values
        if not values:
            return True
        return values[0] == LEADERBOARD_SHOW_VALUE


def preferences_card(
    *,
    default_notifications_enabled: bool = True,
    default_leaderboard_visible: bool = True,
) -> RenderedMessage:
    view = PreferencesView(
        default_notifications_enabled=default_notifications_enabled,
        default_leaderboard_visible=default_leaderboard_visible,
    )
    return RenderedMessage(view=view)


# ---------------------------------------------------------------------------
# Step 7 — Final success card
# ---------------------------------------------------------------------------


def success_card(
    *,
    notifications_enabled: bool = True,
    leaderboard_visible: bool = True,
) -> RenderedMessage:
    """The final clean success card shown after preferences save."""

    view = _layout()
    container = _container(accent_color=COLOR_SUCCESS)
    container.add_item(
        discord.ui.TextDisplay(
            "## And just like that, you’ve now got me tracking your throne sends!"
        )
    )
    container.add_item(
        discord.ui.TextDisplay(
            "Keep in mind I’ll always respect your wishes when it comes to "
            "being notified about a send or being shown on the leaderboard. "
            "And you can always change these settings in future by running "
            "`/settings` in these DM’s or in the server!"
        )
    )
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.TextDisplay(
            "If something stops working or doesn’t appear to be working "
            "correctly, then report it via `/report`!"
        )
    )
    # Tiny status footer reflecting current choices. This is informational
    # only; the spec text above is the authoritative copy.
    notify_line = (
        "📬 DM notifications on" if notifications_enabled else "🔕 DM notifications off"
    )
    lb_line = (
        "👑 Shown on the leaderboard"
        if leaderboard_visible
        else "🔒 Hidden from the leaderboard"
    )
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"-# {notify_line}  •  {lb_line}"))
    view.add_item(container)
    return RenderedMessage(view=view)


# ---------------------------------------------------------------------------
# Migration prompt (already-registered Dom/mes in the test guild)
# ---------------------------------------------------------------------------


class MigrationPromptView(discord.ui.LayoutView):
    """Migration prompt that shows the same preference menus alongside a
    `Defer for 7 days` button."""

    def __init__(
        self,
        *,
        name: str | None = None,
        default_notifications_enabled: bool = True,
        default_leaderboard_visible: bool = True,
    ) -> None:
        super().__init__(timeout=None)
        display = (name or "there").strip() or "there"

        container = discord.ui.Container(accent_color=COLOR_INFO)
        container.add_item(discord.ui.TextDisplay(f"## Hey {display}, Rob here!"))
        container.add_item(
            discord.ui.TextDisplay(
                "As announced by Pat earlier this week, I’ll be changing how "
                "I send you notifications about sends made to you through "
                "automatic tracking."
            )
        )
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("———————"))
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.TextDisplay(
                "Rob can now DM you directly when a send comes in, and you "
                "can also choose whether you appear on the leaderboard or "
                "keep things private."
            )
        )
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("———————"))
        container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.TextDisplay("### 📬 Send notifications"))
        self.notifications_select = discord.ui.Select(
            custom_id=ID_MIGRATION_NOTIFICATIONS,
            placeholder="📬 Send notifications",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="📬 DM me when a send comes in",
                    value=NOTIFY_ON_VALUE,
                    default=default_notifications_enabled,
                ),
                discord.SelectOption(
                    label="🔕 Do not DM me about sends",
                    value=NOTIFY_OFF_VALUE,
                    default=not default_notifications_enabled,
                ),
            ],
        )
        container.add_item(self.notifications_select)
        container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.TextDisplay("### 📊 Leaderboard visibility"))
        self.leaderboard_select = discord.ui.Select(
            custom_id=ID_MIGRATION_LEADERBOARD,
            placeholder="📊 Leaderboard visibility",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="👑 Show me on the leaderboard",
                    value=LEADERBOARD_SHOW_VALUE,
                    default=default_leaderboard_visible,
                ),
                discord.SelectOption(
                    label="🔒 Keep me off the leaderboard",
                    value=LEADERBOARD_HIDE_VALUE,
                    default=not default_leaderboard_visible,
                ),
            ],
        )
        container.add_item(self.leaderboard_select)
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.TextDisplay(
                "-# Please note you can defer for 7 days and we’ll revisit "
                "these settings then."
            )
        )
        container.add_item(discord.ui.Separator())

        save = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Save preferences",
            custom_id=ID_MIGRATION_SAVE,
        )
        defer = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Defer for 7 days",
            custom_id=ID_MIGRATION_DEFER,
        )
        self.save_button = save
        self.defer_button = defer
        # NOTE: legacy IDs kept for back-compat with tests that look for them.
        self.open_prefs_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Open preferences",
            custom_id=ID_MIGRATION_OPEN_PREFS,
        )
        container.add_item(discord.ui.ActionRow(save, defer))
        self.add_item(container)
        # Hidden persistent button so the legacy custom_id is still registered.
        self.add_item(discord.ui.ActionRow(self.open_prefs_button))

    @property
    def chosen_notifications_enabled(self) -> bool:
        values = self.notifications_select.values
        if not values:
            return True
        return values[0] == NOTIFY_ON_VALUE

    @property
    def chosen_leaderboard_visible(self) -> bool:
        values = self.leaderboard_select.values
        if not values:
            return True
        return values[0] == LEADERBOARD_SHOW_VALUE


def migration_prompt_card(
    *,
    name: str | None = None,
    default_notifications_enabled: bool = True,
    default_leaderboard_visible: bool = True,
) -> RenderedMessage:
    view = MigrationPromptView(
        name=name,
        default_notifications_enabled=default_notifications_enabled,
        default_leaderboard_visible=default_leaderboard_visible,
    )
    return RenderedMessage(view=view)


# ---------------------------------------------------------------------------
# Generic small DM error card (used when identity resolution fails, etc.)
# ---------------------------------------------------------------------------


def onboarding_error_card(message: str) -> RenderedMessage:
    """Render a small error card that keeps the intro button so the user
    can re-try the Throne input step."""

    view = _layout()
    container = _container(accent_color=COLOR_WARNING)
    container.add_item(discord.ui.TextDisplay("## Hmm, that didn’t work"))
    container.add_item(discord.ui.TextDisplay(message))
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.TextDisplay(
            "Tap **Enter Throne details** below to try again with your "
            "Throne username or link."
        )
    )
    view.add_item(container)
    button = discord.ui.Button(
        style=discord.ButtonStyle.primary,
        label="Enter Throne details",
        custom_id=ID_INTRO_OPEN_MODAL,
    )
    add_card_actions(view, button)
    return RenderedMessage(view=view)
