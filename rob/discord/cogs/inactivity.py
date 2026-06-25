from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks

from rob.config.guilds import TEST_GUILD_ID, is_test_guild
from rob.discord.permissions import is_staff_member
from rob.ui.cards.errors import error_card
from rob.ui.cards.inactivity import (
    inactivity_empty_list_card,
    inactivity_list_card,
    inactivity_test_sent_card,
)

if TYPE_CHECKING:
    from rob.discord.client import RobBot

log = logging.getLogger(__name__)


class InactivityCog(commands.Cog):
    def __init__(self, bot: "RobBot") -> None:
        self.bot = bot
        self.inactivity_loop.change_interval(minutes=max(1, bot.settings.inactivity_loop_minutes))
        self.inactivity_loop.start()

    def cog_unload(self) -> None:
        self.inactivity_loop.cancel()

    @tasks.loop(minutes=60)
    async def inactivity_loop(self) -> None:
        guild_ids = await self.bot.guild_settings_repo.list_guild_ids()
        for guild_id in guild_ids:
            if not is_test_guild(guild_id):
                continue
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            try:
                await self.bot.inactivity_service.process_guild(
                    guild,
                    send_notifications=True,
                    perform_kicks=True,
                )
            except Exception:  # pragma: no cover - safety logging around runtime loop
                log.exception("Inactivity loop failed for guild_id=%s", guild_id)

    @inactivity_loop.before_loop
    async def _before_inactivity_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def _can_manage(self, user: discord.abc.User, guild: discord.Guild) -> bool:
        owner_id = self.bot.settings.inactivity_owner_user_id
        if owner_id is not None and user.id == owner_id:
            return True
        member = user if isinstance(user, discord.Member) else guild.get_member(user.id)
        settings = await self.bot.guild_settings_repo.get(guild.id)
        if is_staff_member(member, settings):
            return True
        trial_role_id = settings.trial_mod_role_id if settings is not None else None
        return isinstance(member, discord.Member) and any(
            role.id == trial_role_id for role in member.roles if trial_role_id is not None
        )

    @app_commands.command(name="inactivitytest", description="DM the inactivity notice templates to yourself.")
    @app_commands.guilds(TEST_GUILD_ID)
    @app_commands.choices(
        notice_type=[
            app_commands.Choice(name="All notices", value="all"),
            app_commands.Choice(name="First notice", value="first"),
            app_commands.Choice(name="Final notice", value="final"),
        ]
    )
    async def inactivity_test(
        self,
        interaction: discord.Interaction,
        notice_type: app_commands.Choice[str],
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                **error_card("This command can only be used in a server.").send_kwargs(),
                ephemeral=True,
            )
            return
        if not await self._can_manage(interaction.user, interaction.guild):
            await interaction.response.send_message(
                **error_card("Only moderators can run this command.").send_kwargs(),
                ephemeral=True,
            )
            return

        member = (
            interaction.user
            if isinstance(interaction.user, discord.Member)
            else interaction.guild.get_member(interaction.user.id)
        )
        if member is None:
            await interaction.response.send_message(
                **error_card("Rob could not resolve your member record in this server.").send_kwargs(),
                ephemeral=True,
            )
            return

        remove_at = datetime.now(timezone.utc) + timedelta(
            days=self.bot.settings.inactivity_kick_grace_days
        )
        value = notice_type.value
        service = self.bot.inactivity_service
        messages: list[dict[str, object]] = []
        if value in {"all", "first"}:
            messages.append(service._build_first_notice(member, remove_at, interaction.guild.name))
        if value in {"all", "final"}:
            messages.append(service._build_final_notice(member, remove_at, interaction.guild.name))

        for message in messages:
            await member.send(**message)

        await interaction.response.send_message(
            **inactivity_test_sent_card(len(messages)).send_kwargs(),
            ephemeral=True,
        )

    @app_commands.command(name="inactivelist", description="List members on the inactivity removal watchlist.")
    @app_commands.guilds(TEST_GUILD_ID)
    async def inactivity_list(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                **error_card("This command can only be used in a server.").send_kwargs(),
                ephemeral=True,
            )
            return
        if not await self._can_manage(interaction.user, interaction.guild):
            await interaction.response.send_message(
                **error_card("Only moderators can run this command.").send_kwargs(),
                ephemeral=True,
            )
            return

        records = await self.bot.inactive_users_repo.list_for_guild(interaction.guild.id)
        records = [record for record in records if record.remove_at is not None]
        if not records:
            await interaction.response.send_message(
                **inactivity_empty_list_card().send_kwargs(), ephemeral=True
            )
            return

        lines: list[str] = []
        for record in records:
            ts = int(record.remove_at.timestamp())
            lines.append(f"- <@{record.discord_user_id}> (`{record.discord_user_id}`) — remove <t:{ts}:R> / <t:{ts}:F>")
        await interaction.response.send_message(
            **inactivity_list_card(lines[:200], len(records)).send_kwargs(),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if not is_test_guild(after.guild.id):
            return
        settings = await self.bot.guild_settings_repo.get(after.guild.id)
        if settings is None:
            return

        inactive_role_id = settings.inactive_role_id
        unverified_role_id = settings.unverified_role_id

        def _had(role_id: int | None, member: discord.Member) -> bool:
            return role_id is not None and any(role.id == role_id for role in member.roles)

        # Manual removal of the inactive role clears the countdown.
        if _had(inactive_role_id, before) and not _had(inactive_role_id, after):
            await self.bot.inactivity_service.clear_member_state(after.guild.id, after.id)

        # Verifying (losing the unverified role) counts as activity, so the next
        # sweep grants the Active role instead of leaving them parked.
        if _had(unverified_role_id, before) and not _had(unverified_role_id, after):
            await self.bot.inactivity_service.record_activity(after.guild.id, after.id)
            await self.bot.inactivity_service.clear_member_state(after.guild.id, after.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if not is_test_guild(member.guild.id):
            return
        await self.bot.inactivity_service.clear_member_state(member.guild.id, member.id)
