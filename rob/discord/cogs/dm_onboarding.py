"""Runtime interactions for the DM-based Dom/me onboarding flow.

This cog finishes the runtime wiring that PR #13 set up. It is responsible
for:

- handling all onboarding button + modal interactions (with stable custom IDs)
- opening / submitting the Throne input modal
- calling :class:`~rob.services.dm_onboarding_service.DMOnboardingService`
- editing the same DM message through each stage of the flow
- rotating the webhook URL when the user clicks "Doesn’t look to have worked!"
- handling the migration prompt (Save preferences / Defer for 7 days)
- being notified from the webhook handler when a Throne test webhook is
  received, and auto-advancing the DM to the preferences card

All onboarding behavior is gated to ``TEST_GUILD_ID`` (see
:func:`rob.config.guilds.is_test_guild`). Outside the test guild the
existing main-server flow handled by
:class:`rob.discord.cogs.registration.RegistrationCog` keeps running
unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import logging

import discord
from discord.ext import commands

from rob.config.guilds import is_test_guild
from rob.services.dm_onboarding_service import (
    DMOnboardingService,
    OnboardingError,
)
from rob.ui.cards.dm_onboarding import (
    ID_IDENTITY_NO,
    ID_IDENTITY_YES,
    ID_INTRO_MODAL,
    ID_INTRO_MODAL_FIELD,
    ID_INTRO_OPEN_MODAL,
    ID_MIGRATION_DEFER,
    ID_MIGRATION_LEADERBOARD,
    ID_MIGRATION_NOTIFICATIONS,
    ID_MIGRATION_OPEN_PREFS,
    ID_MIGRATION_SAVE,
    ID_PREFS_LEADERBOARD,
    ID_PREFS_NOTIFICATIONS,
    ID_PREFS_SAVE,
    ID_WEBHOOK_RETRY,
    LEADERBOARD_SHOW_VALUE,
    MigrationPromptView,
    NOTIFY_ON_VALUE,
    PreferencesView,
    identity_confirm_card,
    intro_card,
    migration_prompt_card,
    onboarding_error_card,
    preferences_card,
    success_card,
    webhook_setup_card,
)

if TYPE_CHECKING:
    from rob.discord.client import RobBot


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Persistent views
# ---------------------------------------------------------------------------


class _IntroPersistentView(discord.ui.View):
    """Stable view registered at startup so the intro button keeps working
    even after a bot restart (button custom_id is matched, not the view
    instance)."""

    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self.add_item(_OpenModalButton(cog))


class _OpenModalButton(discord.ui.Button):
    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Enter Throne details",
            custom_id=ID_INTRO_OPEN_MODAL,
        )
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_open_modal(interaction)


class _IdentityYesButton(discord.ui.Button):
    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Sure does!",
            custom_id=ID_IDENTITY_YES,
        )
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_identity_yes(interaction)


class _IdentityNoButton(discord.ui.Button):
    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Not quite!",
            custom_id=ID_IDENTITY_NO,
        )
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_identity_no(interaction)


class _WebhookRetryButton(discord.ui.Button):
    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Doesn’t look to have worked!",
            custom_id=ID_WEBHOOK_RETRY,
        )
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_webhook_retry(interaction)


class _SavePrefsButton(discord.ui.Button):
    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Save preferences",
            custom_id=ID_PREFS_SAVE,
        )
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_save_preferences(interaction)


class _MigrationSaveButton(discord.ui.Button):
    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Save preferences",
            custom_id=ID_MIGRATION_SAVE,
        )
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_migration_save(interaction)


class _MigrationDeferButton(discord.ui.Button):
    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Defer for 7 days",
            custom_id=ID_MIGRATION_DEFER,
        )
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_migration_defer(interaction)


class _MigrationOpenPrefsButton(discord.ui.Button):
    """Legacy button kept for back-compat; just sends the migration card again
    so the user gets a fresh interactive prompt."""

    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Open preferences",
            custom_id=ID_MIGRATION_OPEN_PREFS,
        )
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_migration_open_prefs(interaction)


class _PersistentInteractionsView(discord.ui.View):
    """Registers all interactive button custom IDs so persistence works after
    a bot restart. Components V2 LayoutViews are also added separately so
    their selects/buttons are routed correctly."""

    def __init__(self, cog: "DMOnboardingCog") -> None:
        super().__init__(timeout=None)
        self._cog = cog
        self.add_item(_OpenModalButton(cog))
        self.add_item(_IdentityYesButton(cog))
        self.add_item(_IdentityNoButton(cog))
        self.add_item(_WebhookRetryButton(cog))
        self.add_item(_SavePrefsButton(cog))
        self.add_item(_MigrationSaveButton(cog))
        self.add_item(_MigrationDeferButton(cog))
        self.add_item(_MigrationOpenPrefsButton(cog))


# ---------------------------------------------------------------------------
# Modal
# ---------------------------------------------------------------------------


class _ThroneInputModal(discord.ui.Modal, title="Your Throne profile"):
    throne_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Throne username or link",
        placeholder="e.g. yourname  or  https://throne.com/yourname",
        required=True,
        max_length=200,
        custom_id=ID_INTRO_MODAL_FIELD,
    )

    def __init__(self, *, cog: "DMOnboardingCog", guild_id: int) -> None:
        super().__init__(custom_id=ID_INTRO_MODAL)
        self._cog = cog
        self._guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._cog.handle_modal_submit(
            interaction,
            guild_id=self._guild_id,
            throne_input=str(self.throne_input.value),
        )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class DMOnboardingCog(commands.Cog):
    """Runtime cog for the DM-based onboarding flow (test guild only)."""

    def __init__(self, bot: "RobBot") -> None:
        self.bot = bot
        # Track the guild a given Dom/me started onboarding from. Without
        # this we cannot tell from a DM-only interaction which guild the
        # flow belongs to. Persisted via the onboarding state row.
        self._active_intro_views: list[discord.ui.View] = []

    # -- service helper ----------------------------------------------------

    @property
    def service(self) -> DMOnboardingService | None:
        return getattr(self.bot, "dm_onboarding_service", None)

    def _has_service(self, interaction: discord.Interaction | None = None) -> bool:
        return self.service is not None

    # -- view registration -------------------------------------------------

    def register_persistent_views(self) -> None:
        """Register all persistent views so button custom IDs are routable
        after a restart."""

        try:
            self.bot.add_view(_PersistentInteractionsView(self))
        except Exception:
            # add_view in test contexts (mocks) may not support being called;
            # never let that break startup.
            log.debug("Could not register persistent DM onboarding view.", exc_info=True)

    # -- onboarding entry points ------------------------------------------

    async def start_onboarding_dm(
        self,
        *,
        user: discord.abc.User,
        guild_id: int,
    ) -> tuple[bool, discord.Message | None, str | None]:
        """Start the DM-based onboarding flow for ``user``.

        Returns ``(ok, message, error_text)``. The caller (the registration
        cog) is responsible for the ephemeral slash response.
        """

        service = self.service
        if service is None or not is_test_guild(guild_id):
            return False, None, "DM onboarding is not available here."

        try:
            await service.start(guild_id=guild_id, discord_user_id=user.id)
        except OnboardingError as exc:
            return False, None, str(exc)

        rendered = intro_card(name=getattr(user, "display_name", None) or user.name)
        try:
            message = await user.send(**rendered.send_kwargs())
        except discord.Forbidden:
            log.warning(
                "DM onboarding intro could not be sent (forbidden) user_id=%s guild_id=%s",
                user.id,
                guild_id,
            )
            return False, None, "Rob couldn’t DM you. Please allow DMs from this server and try again."
        except discord.HTTPException as exc:
            log.exception(
                "DM onboarding intro send failed user_id=%s guild_id=%s: %s",
                user.id,
                guild_id,
                exc,
            )
            return False, None, "Rob couldn’t send the setup DM right now."

        await self._persist_dm_message(
            guild_id=guild_id,
            discord_user_id=user.id,
            message=message,
        )
        return True, message, None

    async def send_migration_prompt(
        self,
        *,
        user: discord.abc.User,
        guild_id: int,
        default_notifications_enabled: bool = True,
        default_leaderboard_visible: bool = True,
    ) -> discord.Message | None:
        """Send the migration prompt DM to an already-registered Dom/me in
        the test guild. Returns the message (or ``None`` on failure)."""

        if not is_test_guild(guild_id):
            return None
        rendered = migration_prompt_card(
            name=getattr(user, "display_name", None) or user.name,
            default_notifications_enabled=default_notifications_enabled,
            default_leaderboard_visible=default_leaderboard_visible,
        )
        try:
            return await user.send(**rendered.send_kwargs())
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "Migration prompt DM failed user_id=%s guild_id=%s: %s",
                user.id,
                guild_id,
                exc,
            )
            return None

    # -- internal: persist + fetch the in-progress DM message --------------

    async def _persist_dm_message(
        self,
        *,
        guild_id: int,
        discord_user_id: int,
        message: discord.Message,
    ) -> None:
        repo = getattr(self.bot, "domme_onboarding_repo", None)
        if repo is None:
            return
        try:
            await repo.set_dm_message(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                dm_channel_id=int(message.channel.id),
                dm_message_id=int(message.id),
            )
        except Exception:
            log.exception(
                "Failed to persist DM onboarding message ids user_id=%s guild_id=%s",
                discord_user_id,
                guild_id,
            )

    async def _resolve_guild_id_for_user(self, user_id: int) -> int | None:
        """Look up the guild the user's in-progress onboarding belongs to.

        This is necessary because interactions inside a DM channel have no
        ``interaction.guild`` set, so the cog cannot infer the guild any
        other way. The onboarding row stores ``guild_id`` per row.
        """

        repo = getattr(self.bot, "domme_onboarding_repo", None)
        if repo is None:
            return None
        # We don't have a "find by user" API; fall back to test guild only.
        # (The flow is test-guild only by spec; if needed in the future a
        # dedicated lookup can be added.)
        from rob.config.guilds import TEST_GUILD_ID

        try:
            state = await repo.get(
                guild_id=TEST_GUILD_ID,
                discord_user_id=user_id,
            )
        except Exception:
            log.exception("Onboarding state lookup failed user_id=%s", user_id)
            return None
        if state is None:
            return None
        return int(state.guild_id)

    async def _edit_stored_dm(
        self,
        *,
        guild_id: int,
        discord_user_id: int,
        rendered,
    ) -> bool:
        """Edit the stored DM message in place; returns ``True`` on success."""

        repo = getattr(self.bot, "domme_onboarding_repo", None)
        if repo is None:
            return False
        try:
            state = await repo.get(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
            )
        except Exception:
            log.exception(
                "Onboarding state lookup failed during edit user_id=%s guild_id=%s",
                discord_user_id,
                guild_id,
            )
            return False
        if state is None or state.dm_channel_id is None or state.dm_message_id is None:
            log.warning(
                "No stored DM message for onboarding user_id=%s guild_id=%s",
                discord_user_id,
                guild_id,
            )
            return False

        try:
            user = self.bot.get_user(discord_user_id) or await self.bot.fetch_user(
                discord_user_id
            )
            dm_channel = user.dm_channel or await user.create_dm()
            message = dm_channel.get_partial_message(int(state.dm_message_id))
            await message.edit(**rendered.edit_kwargs())
            return True
        except discord.NotFound:
            log.warning(
                "Stored onboarding DM is gone user_id=%s guild_id=%s message_id=%s",
                discord_user_id,
                guild_id,
                state.dm_message_id,
            )
            return False
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "Could not edit stored onboarding DM user_id=%s guild_id=%s: %s",
                discord_user_id,
                guild_id,
                exc,
            )
            return False

    # -- button handlers --------------------------------------------------

    async def handle_open_modal(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id or await self._resolve_guild_id_for_user(
            interaction.user.id
        )
        if guild_id is None or not is_test_guild(guild_id):
            await interaction.response.send_message(
                "This setup isn't available right now.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            _ThroneInputModal(cog=self, guild_id=int(guild_id))
        )

    async def handle_modal_submit(
        self,
        interaction: discord.Interaction,
        *,
        guild_id: int,
        throne_input: str,
    ) -> None:
        service = self.service
        if service is None or not is_test_guild(guild_id):
            await interaction.response.send_message(
                "This setup isn't available right now.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            identity = await service.submit_throne_input(
                guild_id=guild_id,
                discord_user_id=interaction.user.id,
                throne_input=throne_input,
            )
        except OnboardingError as exc:
            rendered = onboarding_error_card(str(exc))
            edited = await self._edit_stored_dm(
                guild_id=guild_id,
                discord_user_id=interaction.user.id,
                rendered=rendered,
            )
            if not edited:
                await interaction.followup.send(str(exc), ephemeral=True)
            else:
                await interaction.followup.send(
                    "Couldn’t resolve that — check your DM and try again.",
                    ephemeral=True,
                )
            return

        rendered = identity_confirm_card(
            throne_handle=identity.throne_handle,
            throne_display_name=identity.throne_display_name,
        )
        ok = await self._edit_stored_dm(
            guild_id=guild_id,
            discord_user_id=interaction.user.id,
            rendered=rendered,
        )
        if not ok:
            # Fall back to a new DM so the flow keeps moving.
            try:
                message = await interaction.user.send(**rendered.send_kwargs())
                await self._persist_dm_message(
                    guild_id=guild_id,
                    discord_user_id=interaction.user.id,
                    message=message,
                )
            except (discord.Forbidden, discord.HTTPException):
                await interaction.followup.send(
                    "Rob couldn’t update your DM. Please re-run /register domme.",
                    ephemeral=True,
                )
                return
        await interaction.followup.send(
            "Got it — check your DMs to confirm.", ephemeral=True
        )

    async def handle_identity_yes(self, interaction: discord.Interaction) -> None:
        guild_id = await self._resolve_guild_id_for_user(interaction.user.id)
        service = self.service
        if guild_id is None or service is None or not is_test_guild(guild_id):
            await interaction.response.send_message(
                "This setup isn't available right now.", ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            webhook_url = await service.confirm_identity(
                guild_id=guild_id,
                discord_user_id=interaction.user.id,
            )
        except OnboardingError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if not webhook_url:
            await interaction.followup.send(
                "Rob couldn’t generate your webhook URL. Ask staff to verify "
                "THRONE_WEBHOOK_BASE_URL on the bot server.",
                ephemeral=True,
            )
            return

        rendered = webhook_setup_card(webhook_url=webhook_url)
        # Append a persistent retry button on this LayoutView so the custom_id
        # routes to the cog.
        from rob.ui.render import add_card_actions

        add_card_actions(rendered.view, _WebhookRetryButton(self))
        await self._edit_or_resend(
            interaction=interaction,
            guild_id=guild_id,
            rendered=rendered,
        )

    async def handle_identity_no(self, interaction: discord.Interaction) -> None:
        guild_id = await self._resolve_guild_id_for_user(interaction.user.id)
        service = self.service
        if guild_id is None or service is None or not is_test_guild(guild_id):
            await interaction.response.send_message(
                "This setup isn't available right now.", ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            await service.reject_identity(
                guild_id=guild_id,
                discord_user_id=interaction.user.id,
            )
        except OnboardingError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        name = getattr(interaction.user, "display_name", None) or interaction.user.name
        rendered = intro_card(name=name)
        await self._edit_or_resend(
            interaction=interaction,
            guild_id=guild_id,
            rendered=rendered,
        )

    async def handle_webhook_retry(self, interaction: discord.Interaction) -> None:
        """User clicked "Doesn’t look to have worked!".

        We rotate the webhook URL (so any leaked/stale URL is invalidated)
        and re-render the same waiting card with the new URL. If rotation
        fails for any reason we fall back to refreshing with whatever URL
        is currently valid so the flow never gets stuck.
        """

        guild_id = await self._resolve_guild_id_for_user(interaction.user.id)
        if guild_id is None or not is_test_guild(guild_id):
            await interaction.response.send_message(
                "This setup isn't available right now.", ephemeral=True
            )
            return

        await interaction.response.defer()
        webhook_url: str | None = None
        registration_service = getattr(self.bot, "registration_service", None)
        if registration_service is not None:
            try:
                result = await registration_service.reissue_domme_webhook(
                    guild_id=guild_id,
                    discord_user_id=interaction.user.id,
                )
                webhook_url = result.webhook_url
            except Exception:
                log.exception(
                    "Webhook reissue failed during onboarding retry user_id=%s guild_id=%s",
                    interaction.user.id,
                    guild_id,
                )

        if not webhook_url:
            # Fall back to the currently-saved URL (rebuild from secret).
            dommes = getattr(self.bot, "dommes_repo", None)
            if dommes is not None and registration_service is not None:
                try:
                    domme = await dommes.get_by_user_id(
                        guild_id, interaction.user.id
                    )
                    if domme is not None and domme.webhook_secret and domme.throne_creator_id:
                        webhook_url = registration_service.build_webhook_url(
                            creator_id=domme.throne_creator_id,
                            webhook_secret=domme.webhook_secret,
                        )
                except Exception:
                    log.exception(
                        "Webhook URL rebuild failed user_id=%s guild_id=%s",
                        interaction.user.id,
                        guild_id,
                    )

        if not webhook_url:
            await interaction.followup.send(
                "Rob couldn’t refresh your webhook URL. Please ask staff.",
                ephemeral=True,
            )
            return

        rendered = webhook_setup_card(webhook_url=webhook_url)
        from rob.ui.render import add_card_actions

        add_card_actions(rendered.view, _WebhookRetryButton(self))
        await self._edit_or_resend(
            interaction=interaction,
            guild_id=guild_id,
            rendered=rendered,
        )

    async def handle_save_preferences(self, interaction: discord.Interaction) -> None:
        guild_id = await self._resolve_guild_id_for_user(interaction.user.id)
        service = self.service
        if guild_id is None or service is None or not is_test_guild(guild_id):
            await interaction.response.send_message(
                "This setup isn't available right now.", ephemeral=True
            )
            return

        # Resolve currently-selected values from the live view, falling back to
        # the message component data when needed.
        notifications_enabled, leaderboard_visible = _read_prefs_from_interaction(
            interaction
        )

        await interaction.response.defer()
        try:
            await service.save_preferences(
                guild_id=guild_id,
                discord_user_id=interaction.user.id,
                notifications_enabled=notifications_enabled,
                leaderboard_visible=leaderboard_visible,
            )
        except OnboardingError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        rendered = success_card(
            notifications_enabled=notifications_enabled,
            leaderboard_visible=leaderboard_visible,
        )
        await self._edit_or_resend(
            interaction=interaction,
            guild_id=guild_id,
            rendered=rendered,
        )

    # -- migration handlers ------------------------------------------------

    async def handle_migration_save(self, interaction: discord.Interaction) -> None:
        guild_id = await self._resolve_guild_id_for_user(interaction.user.id)
        # Migration may run for users who never had an onboarding row, so we
        # also fall back to the test guild constant when nothing is stored.
        if guild_id is None:
            from rob.config.guilds import TEST_GUILD_ID

            guild_id = TEST_GUILD_ID
        if not is_test_guild(guild_id):
            await interaction.response.send_message(
                "This setup isn't available here.", ephemeral=True
            )
            return

        dommes = getattr(self.bot, "dommes_repo", None)
        if dommes is None:
            await interaction.response.send_message(
                "Preferences aren't available right now.", ephemeral=True
            )
            return

        notifications_enabled, leaderboard_visible = _read_prefs_from_interaction(
            interaction
        )
        await interaction.response.defer()
        try:
            await dommes.set_preferences(
                guild_id=guild_id,
                discord_user_id=interaction.user.id,
                send_notifications_enabled=notifications_enabled,
                leaderboard_visible=leaderboard_visible,
                clear_defer=True,
                confirm=True,
            )
        except Exception:
            log.exception(
                "Migration save_preferences failed user_id=%s guild_id=%s",
                interaction.user.id,
                guild_id,
            )
            await interaction.followup.send(
                "Rob couldn’t save those preferences.", ephemeral=True
            )
            return

        rendered = success_card(
            notifications_enabled=notifications_enabled,
            leaderboard_visible=leaderboard_visible,
        )
        try:
            if interaction.message is not None:
                await interaction.message.edit(**rendered.edit_kwargs())
            else:
                await interaction.followup.send(**rendered.send_kwargs())
        except (discord.NotFound, discord.HTTPException):
            log.exception(
                "Migration success card edit failed user_id=%s guild_id=%s",
                interaction.user.id,
                guild_id,
            )

    async def handle_migration_defer(self, interaction: discord.Interaction) -> None:
        guild_id = await self._resolve_guild_id_for_user(interaction.user.id)
        if guild_id is None:
            from rob.config.guilds import TEST_GUILD_ID

            guild_id = TEST_GUILD_ID
        if not is_test_guild(guild_id):
            await interaction.response.send_message(
                "This setup isn't available here.", ephemeral=True
            )
            return

        service = self.service
        if service is None:
            await interaction.response.send_message(
                "Defer isn't available right now.", ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            await service.defer_migration(
                guild_id=guild_id,
                discord_user_id=interaction.user.id,
                days=7,
            )
        except OnboardingError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        # Acknowledge with a small inline edit; the existing migration card
        # stays in place so the user can still set preferences later.
        try:
            await interaction.followup.send(
                "No worries — Rob will check back in with you in 7 days.",
                ephemeral=True,
            )
        except discord.HTTPException:
            pass

    async def handle_migration_open_prefs(
        self, interaction: discord.Interaction
    ) -> None:
        # Legacy path: just re-render the migration card.
        name = getattr(interaction.user, "display_name", None) or interaction.user.name
        rendered = migration_prompt_card(name=name)
        try:
            await interaction.response.edit_message(**rendered.edit_kwargs())
        except discord.HTTPException:
            try:
                await interaction.response.send_message(
                    **rendered.send_kwargs(), ephemeral=True
                )
            except discord.HTTPException:
                log.exception("Could not re-send migration prompt.")

    # -- webhook auto-advance hook (called from bot ops endpoint) ----------

    async def on_throne_test_webhook_received(
        self,
        *,
        guild_id: int,
        discord_user_id: int,
    ) -> bool:
        """Called when a Throne test webhook arrives for a Dom/me currently
        in onboarding in the test guild. Advances the DM to the preferences
        step. Returns ``True`` if the DM was edited."""

        service = self.service
        if service is None or not is_test_guild(guild_id):
            return False

        repo = getattr(self.bot, "domme_onboarding_repo", None)
        if repo is None:
            return False
        try:
            state = await repo.get(
                guild_id=guild_id, discord_user_id=discord_user_id
            )
        except Exception:
            log.exception(
                "Auto-advance lookup failed user_id=%s guild_id=%s",
                discord_user_id,
                guild_id,
            )
            return False
        if state is None or state.stage == "completed":
            return False
        # The expected stage is ``awaiting_webhook``; if we're already in
        # ``awaiting_preferences`` re-rendering is still a safe no-op.
        try:
            await service.mark_webhook_received(
                guild_id=guild_id, discord_user_id=discord_user_id
            )
        except OnboardingError:
            return False

        rendered = preferences_card()
        # Bind the save button's callback to this cog by adding our own
        # routing button view alongside the LayoutView's Save button. The
        # Save button inside the LayoutView already has the stable custom_id
        # so the persistent view will route it.
        return await self._edit_stored_dm(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            rendered=rendered,
        )

    # -- internal: edit or resend the DM ----------------------------------

    async def _edit_or_resend(
        self,
        *,
        interaction: discord.Interaction,
        guild_id: int,
        rendered,
    ) -> None:
        """Edit the stored DM in place; if that fails, send a fresh DM and
        update the stored ids."""

        if await self._edit_stored_dm(
            guild_id=guild_id,
            discord_user_id=interaction.user.id,
            rendered=rendered,
        ):
            return

        # Fallback: edit the message that triggered the interaction if it is
        # the DM we're tracking. Otherwise send a new DM.
        try:
            if interaction.message is not None and isinstance(
                interaction.channel, discord.DMChannel
            ):
                await interaction.message.edit(**rendered.edit_kwargs())
                await self._persist_dm_message(
                    guild_id=guild_id,
                    discord_user_id=interaction.user.id,
                    message=interaction.message,
                )
                return
        except discord.HTTPException:
            log.exception(
                "Could not edit triggering DM message user_id=%s guild_id=%s",
                interaction.user.id,
                guild_id,
            )

        try:
            message = await interaction.user.send(**rendered.send_kwargs())
            await self._persist_dm_message(
                guild_id=guild_id,
                discord_user_id=interaction.user.id,
                message=message,
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "Fallback DM send failed user_id=%s guild_id=%s: %s",
                interaction.user.id,
                guild_id,
                exc,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_prefs_from_interaction(
    interaction: discord.Interaction,
) -> tuple[bool, bool]:
    """Pull current preference selections off the interaction.

    Reads from the live ``PreferencesView`` / ``MigrationPromptView`` if the
    button belongs to one, falling back to scanning the message's component
    data for select state. Defaults to ``(True, True)``.
    """

    notifications_enabled = True
    leaderboard_visible = True

    view = getattr(interaction, "view", None)
    if isinstance(view, (PreferencesView, MigrationPromptView)):
        return view.chosen_notifications_enabled, view.chosen_leaderboard_visible

    message = getattr(interaction, "message", None)
    if message is None:
        return notifications_enabled, leaderboard_visible
    for row in getattr(message, "components", []) or []:
        for child in getattr(row, "children", []) or []:
            custom_id = getattr(child, "custom_id", None)
            if custom_id in (ID_PREFS_NOTIFICATIONS, ID_MIGRATION_NOTIFICATIONS):
                values = getattr(child, "values", []) or []
                if values:
                    notifications_enabled = values[0] == NOTIFY_ON_VALUE
            elif custom_id in (ID_PREFS_LEADERBOARD, ID_MIGRATION_LEADERBOARD):
                values = getattr(child, "values", []) or []
                if values:
                    leaderboard_visible = values[0] == LEADERBOARD_SHOW_VALUE
    return notifications_enabled, leaderboard_visible


async def setup(bot: "RobBot") -> None:
    cog = DMOnboardingCog(bot)
    await bot.add_cog(cog)
    cog.register_persistent_views()
