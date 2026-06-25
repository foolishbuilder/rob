from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from rob.config.guilds import is_test_guild

if TYPE_CHECKING:
    from rob.discord.client import RobBot

log = logging.getLogger(__name__)


class ActivityTrackerCog(commands.Cog):
    """Records member activity (messages, reactions, interactions) so the
    inactivity system can tell active members from inactive ones.

    Scoped to the test guild while the activity / inactive-role system is rolled
    out there first."""

    def __init__(self, bot: "RobBot") -> None:
        self.bot = bot

    async def _record(self, guild_id: int | None, user: discord.abc.User | None) -> None:
        if guild_id is None or not is_test_guild(guild_id):
            return
        if user is None or user.bot:
            return
        service = getattr(self.bot, "inactivity_service", None)
        if service is None:
            return
        try:
            await service.record_activity(guild_id, user.id)
        except Exception:  # pragma: no cover - never let tracking break event handling
            log.exception("Failed to record activity for user_id=%s guild_id=%s", user.id, guild_id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return
        await self._record(message.guild.id, message.author)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None:
            return
        user = payload.member
        if user is None and payload.user_id:
            user = self.bot.get_user(payload.user_id)
        await self._record(payload.guild_id, user)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        await self._record(interaction.guild_id, interaction.user)
