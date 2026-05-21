from __future__ import annotations

import logging

import discord

from rob.database.repositories.guild_settings import GuildSettingsRepository
from rob.database.repositories.leaderboards import LeaderboardsRepository
from rob.ui.cards.leaderboard import leaderboard_card

log = logging.getLogger(__name__)


class LeaderboardService:
    def __init__(
        self,
        *,
        bot: discord.Client,
        guild_settings: GuildSettingsRepository,
        leaderboards: LeaderboardsRepository,
    ) -> None:
        self.bot = bot
        self.guild_settings = guild_settings
        self.leaderboards = leaderboards

    async def refresh_all_guilds(self) -> None:
        for guild_id in await self.guild_settings.list_guild_ids():
            await self.refresh_guild(guild_id)

    async def refresh_guild(self, guild_id: int) -> bool:
        settings = await self.guild_settings.get(guild_id)
        if settings is None or settings.leaderboard_channel_id is None:
            return False

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            log.warning("Guild %s is not available for leaderboard refresh.", guild_id)
            return False

        channel = guild.get_channel(settings.leaderboard_channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(settings.leaderboard_channel_id)
            except (discord.NotFound, discord.HTTPException):
                log.warning(
                    "Leaderboard channel %s is unavailable in guild %s.",
                    settings.leaderboard_channel_id,
                    guild_id,
                )
                return False
        if not isinstance(channel, discord.TextChannel):
            return False

        summary = await self.leaderboards.get_summary(guild_id)
        dommes = await self.leaderboards.get_top_dommes(guild_id)
        subs = await self.leaderboards.get_top_subs(guild_id)

        dommes_msg = leaderboard_card(
            title="Dom/me Sends Leaderboard",
            entries=dommes,
            summary=summary,
            footer="To join the leaderboard and make it into the top 10, run /register domme.",
        )
        subs_msg = leaderboard_card(
            title="Sub Sends Leaderboard",
            entries=subs,
            summary=summary,
            footer="Sub leaderboard updates from tracked sends.",
        )

        await self._upsert_message(
            guild_id=guild_id,
            channel=channel,
            message_key="dommes",
            leaderboard_type="dommes",
            rendered=dommes_msg,
        )
        await self._upsert_message(
            guild_id=guild_id,
            channel=channel,
            message_key="subs",
            leaderboard_type="subs",
            rendered=subs_msg,
        )
        return True

    async def _upsert_message(
        self,
        *,
        guild_id: int,
        channel: discord.TextChannel,
        message_key: str,
        leaderboard_type: str,
        rendered,
    ) -> None:
        ref = await self.leaderboards.get_message(guild_id, message_key)
        message: discord.Message | None = None
        if ref is not None:
            try:
                message = await channel.fetch_message(ref.message_id)
            except (discord.NotFound, discord.HTTPException):
                message = None
        if message is None:
            message = await channel.send(**rendered.send_kwargs())
        else:
            await message.edit(**rendered.edit_kwargs())
        await self.leaderboards.upsert_message(
            guild_id=guild_id,
            message_key=message_key,
            leaderboard_type=leaderboard_type,
            channel_id=channel.id,
            message_id=message.id,
        )
