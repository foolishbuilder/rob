"""Activity / inactive-role lifecycle.

A verified member who goes ``inactive_after_days`` without sending a message or
otherwise interacting loses the **Active** role, gains the **Inactive** role, and
is placed on the removal countdown: a first notice immediately, a final notice
``final_notice_days`` before removal, and a kick once ``remove_at`` passes. The
moment they interact again the activity tracker refreshes their timestamp and the
next sweep restores the Active role and clears the countdown.

Members holding the **Unverified** role are parked as inactive (Inactive role on,
Active role off) but are never put on the kick countdown — they are new and have
simply not verified yet. Once the Unverified role is gone the normal rules apply.

The activity *signal* (``activity:{guild}:user:{uid}:last_active``) is written by
the activity tracker into ``bot_settings``; the per-member countdown lives in the
``inactive_users`` table.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import discord

from rob.database.repositories.bot_state import BotStateRepository
from rob.database.repositories.guild_settings import GuildSettingsRepository
from rob.database.repositories.inactive_users import InactiveUsersRepository
from rob.services.maintenance_service import MaintenanceService
from rob.ui.cards.inactivity import (
    final_inactivity_warning_card,
    first_inactivity_warning_card,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class InactivitySnapshot:
    member: discord.Member
    remove_at: datetime


class InactivityService:
    def __init__(
        self,
        *,
        bot_state: BotStateRepository,
        guild_settings: GuildSettingsRepository,
        inactive_users: InactiveUsersRepository,
        enabled_default: bool,
        inactive_after_days: int,
        kick_grace_days: int,
        bootstrap_grace_days: int,
        final_notice_days: int,
        notice_channel_id: int | None,
        maintenance: MaintenanceService | None = None,
    ) -> None:
        self.bot_state = bot_state
        self.guild_settings = guild_settings
        self.inactive_users = inactive_users
        self.enabled_default = enabled_default
        self.inactive_after = timedelta(days=max(1, inactive_after_days))
        self.kick_grace = timedelta(days=max(1, kick_grace_days))
        self.bootstrap_grace = timedelta(days=max(1, bootstrap_grace_days))
        self.final_notice_window = timedelta(days=max(1, final_notice_days))
        self.notice_channel_id = notice_channel_id
        self.maintenance = maintenance

    # -- keys -----------------------------------------------------------------

    @staticmethod
    def activity_key(guild_id: int, member_id: int) -> str:
        return f"activity:{guild_id}:user:{member_id}:last_active"

    def _enabled_key(self, guild_id: int) -> str:
        return f"inactivity:{guild_id}:enabled"

    def _bootstrapped_key(self, guild_id: int) -> str:
        return f"inactivity:{guild_id}:bootstrapped_at"

    # -- enable / activity ----------------------------------------------------

    async def is_enabled(self, guild_id: int) -> bool:
        value = await self.bot_state.get_text(self._enabled_key(guild_id))
        return self._parse_bool(value, default=self.enabled_default)

    async def set_enabled(self, guild_id: int, enabled: bool) -> None:
        await self.bot_state.set_value(self._enabled_key(guild_id), "true" if enabled else "false")

    async def record_activity(
        self,
        guild_id: int,
        member_id: int,
        *,
        when: datetime | None = None,
    ) -> None:
        moment = when or datetime.now(timezone.utc)
        await self.bot_state.set_value(self.activity_key(guild_id, member_id), moment.isoformat())

    async def get_last_activity(self, guild_id: int, member_id: int) -> datetime | None:
        return self._parse_optional_datetime(
            await self.bot_state.get_text(self.activity_key(guild_id, member_id))
        )

    async def clear_member_state(self, guild_id: int, member_id: int) -> None:
        await self.inactive_users.clear(guild_id, member_id)

    # -- parsing helpers ------------------------------------------------------

    @staticmethod
    def _parse_bool(raw: str | None, *, default: bool = False) -> bool:
        if raw is None:
            return default
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        return default

    @staticmethod
    def _parse_optional_datetime(raw: str | None) -> datetime | None:
        if raw is None:
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _is_eligible_member(member: discord.Member) -> bool:
        return not member.bot

    @staticmethod
    def _has_role(member: discord.Member, role_id: int | None) -> bool:
        if role_id is None:
            return False
        return any(role.id == role_id for role in getattr(member, "roles", []))

    def _notice_channel_hint(self) -> str:
        if self.notice_channel_id:
            return f"<#{self.notice_channel_id}>"
        return "the server chat"

    @staticmethod
    def _display_name(member: discord.Member) -> str:
        return (getattr(member, "nick", None) or member.display_name or member.name or "").strip() or member.name

    # -- notice builders (also used by /inactivitytest) -----------------------

    def _build_first_notice(self, member: discord.Member, remove_at: datetime, guild_name: str) -> dict[str, object]:
        return first_inactivity_warning_card(
            display_name=self._display_name(member),
            server_name=guild_name,
            remove_at_unix=int(remove_at.timestamp()),
            main_chat_channel=self._notice_channel_hint(),
        ).send_kwargs()

    def _build_final_notice(self, member: discord.Member, remove_at: datetime, guild_name: str) -> dict[str, object]:
        return final_inactivity_warning_card(
            display_name=self._display_name(member),
            server_name=guild_name,
            remove_at_unix=int(remove_at.timestamp()),
            main_chat_channel=self._notice_channel_hint(),
        ).send_kwargs()

    async def _send_dm(self, member: discord.Member, *, message_kwargs: dict[str, object], label: str) -> bool:
        try:
            await member.send(**message_kwargs)
            log.info("Sent inactivity %s DM to user_id=%s", label, member.id)
            return True
        except discord.Forbidden:
            log.info("Could not DM user_id=%s for inactivity %s (DMs closed).", member.id, label)
        except discord.HTTPException:
            log.warning("Failed to DM user_id=%s for inactivity %s", member.id, label, exc_info=True)
        return False

    # -- role plumbing --------------------------------------------------------

    async def _add_role(self, member: discord.Member, role: discord.Role | None, *, reason: str) -> None:
        if role is None or self._has_role(member, role.id):
            return
        try:
            await member.add_roles(role, reason=reason)
            log.info("Added role %s to user_id=%s guild_id=%s", role.id, member.id, member.guild.id)
        except discord.Forbidden:
            log.warning("Missing permission to add role %s to user_id=%s", role.id, member.id)
        except discord.HTTPException:
            log.warning("Failed to add role %s to user_id=%s", role.id, member.id, exc_info=True)

    async def _remove_role(self, member: discord.Member, role: discord.Role | None, *, reason: str) -> None:
        if role is None or not self._has_role(member, role.id):
            return
        try:
            await member.remove_roles(role, reason=reason)
            log.info("Removed role %s from user_id=%s guild_id=%s", role.id, member.id, member.guild.id)
        except discord.Forbidden:
            log.warning("Missing permission to remove role %s from user_id=%s", role.id, member.id)
        except discord.HTTPException:
            log.warning("Failed to remove role %s from user_id=%s", role.id, member.id, exc_info=True)

    # -- main sweep -----------------------------------------------------------

    async def process_guild(
        self,
        guild: discord.Guild,
        *,
        send_notifications: bool,
        perform_kicks: bool,
    ) -> list[InactivitySnapshot]:
        guild_id = guild.id
        if not await self.is_enabled(guild_id):
            return []
        if self.maintenance is not None and await self.maintenance.notifications_suppressed():
            send_notifications = False
            perform_kicks = False

        settings = await self.guild_settings.get(guild_id)
        if settings is None:
            return []
        active_role = guild.get_role(settings.active_role_id) if settings.active_role_id else None
        inactive_role = guild.get_role(settings.inactive_role_id) if settings.inactive_role_id else None
        unverified_role = guild.get_role(settings.unverified_role_id) if settings.unverified_role_id else None
        # Both the active and inactive roles must exist for the swap to mean anything.
        if active_role is None or inactive_role is None:
            return []

        now = datetime.now(timezone.utc)
        bootstrapped_at = self._parse_optional_datetime(
            await self.bot_state.get_text(self._bootstrapped_key(guild_id))
        )
        is_bootstrap_run = bootstrapped_at is None
        grace = self.bootstrap_grace if is_bootstrap_run else self.kick_grace

        snapshots: list[InactivitySnapshot] = []
        for member in guild.members:
            if not self._is_eligible_member(member):
                continue

            # Unverified members are parked as inactive, never on the kick clock.
            if unverified_role is not None and self._has_role(member, unverified_role.id):
                await self._remove_role(member, active_role, reason="Unverified member parked as inactive")
                await self._add_role(member, inactive_role, reason="Unverified member parked as inactive")
                await self.inactive_users.clear(guild_id, member.id)
                continue

            last_activity = await self.get_last_activity(guild_id, member.id)
            effective_last = last_activity
            if effective_last is None:
                joined = getattr(member, "joined_at", None)
                effective_last = joined if joined is not None and joined.tzinfo is not None else now

            is_inactive = (now - effective_last) >= self.inactive_after

            if not is_inactive:
                # Active member: ensure Active on, Inactive off, countdown cleared.
                await self._remove_role(member, inactive_role, reason="Member is active again")
                await self._add_role(member, active_role, reason="Member is active")
                await self.inactive_users.clear(guild_id, member.id)
                continue

            # Inactive member: swap roles and ensure they are on the countdown.
            await self._remove_role(member, active_role, reason="Member inactive for a week")
            await self._add_role(member, inactive_role, reason="Member inactive for a week")

            record = await self.inactive_users.get(guild_id, member.id)
            if record is None or record.remove_at is None:
                remove_at = now + grace
                record = await self.inactive_users.start_watching(
                    guild_id=guild_id,
                    discord_user_id=member.id,
                    inactive_role_assigned_at=now,
                    remove_at=remove_at,
                )
            remove_at = record.remove_at or (now + grace)

            if send_notifications and not record.initial_notice_sent:
                await self._send_dm(
                    member,
                    message_kwargs=self._build_first_notice(member, remove_at, guild.name),
                    label="first-notice",
                )
                await self.inactive_users.mark_initial_notice(guild_id, member.id)

            if perform_kicks and now >= remove_at:
                try:
                    await member.kick(reason=f"Inactive member auto-removal (scheduled {remove_at.isoformat()})")
                    await self.inactive_users.clear(guild_id, member.id)
                    log.info("Kicked inactive member user_id=%s guild_id=%s", member.id, guild_id)
                except discord.Forbidden:
                    log.warning("Missing permission to kick inactive user_id=%s guild_id=%s", member.id, guild_id)
                except discord.HTTPException:
                    log.warning("Failed to kick inactive user_id=%s guild_id=%s", member.id, guild_id, exc_info=True)
                continue

            if (
                send_notifications
                and not record.final_notice_sent
                and now < remove_at
                and (remove_at - now) <= self.final_notice_window
            ):
                await self._send_dm(
                    member,
                    message_kwargs=self._build_final_notice(member, remove_at, guild.name),
                    label="final-notice",
                )
                await self.inactive_users.mark_final_notice(guild_id, member.id)

            snapshots.append(InactivitySnapshot(member=member, remove_at=remove_at))

        if is_bootstrap_run:
            await self.bot_state.set_value(self._bootstrapped_key(guild_id), now.isoformat())
        return snapshots
