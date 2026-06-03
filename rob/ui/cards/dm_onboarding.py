"""Components V2 cards for the DM-based Dom/me onboarding flow.

All cards here are test-guild-only. The cards themselves are dumb renderers
— gating to ``is_test_guild`` is the caller's responsibility. The interaction
handlers live in ``rob.discord.cogs.dm_onboarding`` and the orchestration
in ``rob.services.dm_onboarding_service``.

Each card returns either a :class:`~rob.ui.render.RenderedMessage` or a
:class:`discord.ui.LayoutView` that the caller can ``message.edit(view=...)``
to update the same DM message as the flow progresses.
"""

from __future__ import annotations

import discord

from rob.ui.components import make_card, render
from rob.ui.render import CardSection, RenderedMessage, add_card_actions
from rob.ui.theme import COLOR_INFO, COLOR_SUCCESS, COLOR_WARNING


# ---------------------------------------------------------------------------
# Custom IDs - kept stable so views can be re-bound after a restart.
# ---------------------------------------------------------------------------
ONBOARDING_PREFIX = "rob:dm_onboarding:"
ID_INTRO_OPEN_MODAL = f"{ONBOARDING_PREFIX}intro:open_modal"
ID_INTRO_MODAL = f"{ONBOARDING_PREFIX}intro:modal"
ID_INTRO_MODAL_FIELD = f"{ONBOARDING_PREFIX}intro:modal:throne_input"
ID_IDENTITY_YES = f"{ONBOARDING_PREFIX}identity:yes"
ID_IDENTITY_NO = f"{ONBOARDING_PREFIX}identity:no"
ID_PREFS_NOTIFICATIONS = f"{ONBOARDING_PREFIX}prefs:notifications"
ID_PREFS_LEADERBOARD = f"{ONBOARDING_PREFIX}prefs:leaderboard"
ID_PREFS_SAVE = f"{ONBOARDING_PREFIX}prefs:save"

MIGRATION_PREFIX = "rob:dm_migration:"
ID_MIGRATION_OPEN_PREFS = f"{MIGRATION_PREFIX}open_prefs"
ID_MIGRATION_DEFER = f"{MIGRATION_PREFIX}defer_7d"

# Preference option values stored on the SelectOption.
NOTIFY_ON_VALUE = "notify_on"
NOTIFY_OFF_VALUE = "notify_off"
LEADERBOARD_SHOW_VALUE = "leaderboard_show"
LEADERBOARD_HIDE_VALUE = "leaderboard_hide"


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


def intro_card() -> RenderedMessage:
    """Stage 1: ask the Dom/me for their Throne username or link."""

    card = make_card(
        title="Welcome — let's get you set up",
        body=(
            "Rob will track your Throne sends and DM you when they arrive.\n\n"
            "To get started, share your Throne profile."
        ),
        eyebrow="Rob | Dom/me Setup (DM)",
        callout="Tap the button below and paste your Throne username or link.",
        color=COLOR_INFO,
        variant="setup",
    )
    rendered = render(card)
    button = discord.ui.Button(
        style=discord.ButtonStyle.primary,
        label="Enter Throne profile",
        custom_id=ID_INTRO_OPEN_MODAL,
    )
    assert isinstance(rendered.view, discord.ui.LayoutView)
    add_card_actions(rendered.view, button)
    return rendered


def build_intro_modal() -> discord.ui.Modal:
    """Modal that captures the Throne username or link."""

    class _ThroneInputModal(discord.ui.Modal, title="Your Throne profile"):
        throne_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Throne username or full link",
            placeholder="e.g. yourname  or  https://throne.com/yourname",
            required=True,
            max_length=200,
            custom_id=ID_INTRO_MODAL_FIELD,
        )

        def __init__(self) -> None:
            super().__init__(custom_id=ID_INTRO_MODAL)

    return _ThroneInputModal()


def identity_confirm_card(
    *,
    throne_handle: str,
    throne_display_name: str | None,
) -> RenderedMessage:
    """Stage 2: confirm the Throne identity Rob resolved."""

    display = throne_display_name or throne_handle
    sections = [
        ("Throne username", f"`{throne_handle}`"),
        ("Name as it appears on Throne", display),
    ]
    card = make_card(
        title="Is this you?",
        body="Double-check the details below before we continue.",
        eyebrow="Rob | Identity check",
        sections=[CardSection(title=title, text=text) for title, text in sections],
        color=COLOR_INFO,
        variant="setup",
    )
    rendered = render(card)
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
    assert isinstance(rendered.view, discord.ui.LayoutView)
    add_card_actions(rendered.view, yes, no)
    return rendered


def webhook_setup_card(*, webhook_url: str) -> RenderedMessage:
    """Stage 3: tell the user to paste the webhook URL into Throne and
    send a test event. Rob waits on this same message."""

    card = make_card(
        title="Connect your Throne webhook",
        body=(
            "Open Throne → Settings → Webhooks, paste the URL below, and "
            "send a **Test webhook**.\n\n"
            "Keep this URL private. Rob will edit this message as soon as "
            "the test arrives."
        ),
        eyebrow="Rob | Webhook setup",
        code_block=webhook_url,
        callout="Waiting for your test webhook…",
        color=COLOR_WARNING,
        variant="setup",
    )
    return render(card)


def webhook_waiting_card() -> RenderedMessage:
    """Lightweight 'still waiting' refresh of the webhook card."""

    return webhook_setup_card(webhook_url="(your webhook URL above)")


class PreferencesView(discord.ui.LayoutView):
    """Stage 4: notification + leaderboard preferences via Components V2.

    Uses one :class:`~discord.ui.Select` per preference inside a
    :class:`~discord.ui.Container`, with a Save button to commit. Selections
    are stored on the view instance so the cog can read them when the Save
    button fires.
    """

    def __init__(
        self,
        *,
        default_notifications_enabled: bool = True,
        default_leaderboard_visible: bool = True,
    ) -> None:
        super().__init__(timeout=1800)

        # Build the Container of preference selects.
        container = discord.ui.Container(accent_color=COLOR_INFO)
        container.add_item(discord.ui.TextDisplay("## Your preferences"))
        container.add_item(
            discord.ui.TextDisplay(
                "Choose how Rob notifies you and whether you appear on the leaderboard. "
                "You can change these any time with `/settings`."
            )
        )
        container.add_item(discord.ui.Separator())

        self.notifications_select = discord.ui.Select(
            custom_id=ID_PREFS_NOTIFICATIONS,
            placeholder="Send notifications",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="DM me when a send comes in",
                    value=NOTIFY_ON_VALUE,
                    description="Rob will DM you for each new tracked send.",
                    emoji="📬",
                    default=default_notifications_enabled,
                ),
                discord.SelectOption(
                    label="Do not DM me about sends",
                    value=NOTIFY_OFF_VALUE,
                    description="Sends are still tracked, just no DM.",
                    emoji="🔕",
                    default=not default_notifications_enabled,
                ),
            ],
        )
        container.add_item(self.notifications_select)
        container.add_item(discord.ui.Separator())

        self.leaderboard_select = discord.ui.Select(
            custom_id=ID_PREFS_LEADERBOARD,
            placeholder="Leaderboard visibility",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="Show me on the leaderboard",
                    value=LEADERBOARD_SHOW_VALUE,
                    description="You appear publicly on the in-server leaderboard.",
                    emoji="👑",
                    default=default_leaderboard_visible,
                ),
                discord.SelectOption(
                    label="Keep me off the leaderboard",
                    value=LEADERBOARD_HIDE_VALUE,
                    description="Your sends are still tracked but hidden from the leaderboard.",
                    emoji="🔒",
                    default=not default_leaderboard_visible,
                ),
            ],
        )
        container.add_item(self.leaderboard_select)
        container.add_item(discord.ui.Separator())

        save = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Save preferences",
            custom_id=ID_PREFS_SAVE,
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


def success_card(*, notifications_enabled: bool, leaderboard_visible: bool) -> RenderedMessage:
    notify_line = (
        "📬 You'll get a DM for each new tracked send."
        if notifications_enabled
        else "🔕 DM notifications are off."
    )
    leaderboard_line = (
        "👑 You'll appear on the leaderboard."
        if leaderboard_visible
        else "🔒 You'll be hidden from the leaderboard."
    )
    card = make_card(
        title="You're all set!",
        body=f"{notify_line}\n{leaderboard_line}",
        eyebrow="Rob | Setup complete",
        callout="Run `/settings` any time to change these.",
        color=COLOR_SUCCESS,
        variant="success",
    )
    return render(card)


# ---------------------------------------------------------------------------
# Migration prompt (for already-registered Dom/mes)
# ---------------------------------------------------------------------------


def migration_prompt_card() -> RenderedMessage:
    """DM card sent to already-registered Dom/mes asking them to set
    notification + leaderboard preferences, or defer for 7 days."""

    card = make_card(
        title="New: choose how Rob notifies you",
        body=(
            "Rob now DMs Dom/mes about new sends. Take a moment to choose "
            "your notification and leaderboard preferences, or defer this "
            "for a week."
        ),
        eyebrow="Rob | Preferences update",
        callout="You can always change these later with `/settings`.",
        color=COLOR_INFO,
        variant="setup",
    )
    rendered = render(card)
    open_btn = discord.ui.Button(
        style=discord.ButtonStyle.primary,
        label="Set my preferences",
        custom_id=ID_MIGRATION_OPEN_PREFS,
    )
    defer_btn = discord.ui.Button(
        style=discord.ButtonStyle.secondary,
        label="Defer for 7 days",
        custom_id=ID_MIGRATION_DEFER,
    )
    assert isinstance(rendered.view, discord.ui.LayoutView)
    add_card_actions(rendered.view, open_btn, defer_btn)
    return rendered
