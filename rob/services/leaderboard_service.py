from __future__ import annotations

import logging

import discord

from rob.database.repositories.bot_state import BotStateRepository
from rob.database.repositories.guild_settings import GuildSettingsRepository
from rob.database.repositories.leaderboards import LeaderboardsRepository
from rob.ui.cards.leader_alert import leader_alert_card
from rob.ui.cards.leaderboard import leaderboard_card, leaderboard_stats_card
from rob.services.maintenance_service import MaintenanceService

log = logging.getLogger(__name__)


class LeaderboardService:
    def __init__(
        self,
        *,
        bot: discord.Client,
        guild_settings: GuildSettingsRepository,
        leaderboards: LeaderboardsRepository,
        bot_state: BotStateRepository,
        maintenance: MaintenanceService,
        leaderboard_limit: int = 10,
        include_test_sends: bool = False,
        test_gifter_usernames: tuple[str, ...] = (),
        owner_test_user_id: int | None = None,
    ) -> None:
        self.bot = bot
        self.guild_settings = guild_settings
        self.leaderboards = leaderboards
        self.bot_state = bot_state
        self.maintenance = maintenance
        self.leaderboard_limit = leaderboard_limit
        self.include_test_sends = include_test_sends
        self.test_gifter_usernames = test_gifter_usernames
        self.owner_test_user_id = owner_test_user_id

    async def refresh_all_guilds(self) -> None:
        for guild_id in await self.guild_settings.list_guild_ids():
            await self.refresh_guild(guild_id)

    async def refresh_guild(self, guild_id: int) -> bool:
        log.info("Refreshing leaderboard for guild_id=%s", guild_id)
        settings = await self.guild_settings.get(guild_id)
        if settings is None or settings.leaderboard_channel_id is None:
            log.warning("Skipping leaderboard refresh for guild_id=%s: leaderboard channel not configured.", guild_id)
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
            log.warning(
                "Skipping leaderboard refresh for guild_id=%s: leaderboard channel %s is not a text channel.",
                guild_id,
                settings.leaderboard_channel_id,
            )
            return False

        summary = await self.leaderboards.get_summary(
            guild_id,
            include_test_sends=self.include_test_sends,
            test_gifter_usernames=self.test_gifter_usernames,
            owner_test_user_id=self.owner_test_user_id,
        )
        log.info(
            "Registered Dom/mes loaded=%s guild_id=%s",
            summary.domme_count,
            guild_id,
        )
        dommes = await self.leaderboards.get_top_dommes(
            guild_id,
            limit=self.leaderboard_limit,
            include_test_sends=self.include_test_sends,
            test_gifter_usernames=self.test_gifter_usernames,
            owner_test_user_id=self.owner_test_user_id,
        )
        log.info(
            "Leaderboard entries rendered=%s leaderboard_limit=%s guild_id=%s",
            len(dommes),
            self.leaderboard_limit,
            guild_id,
        )
        dommes_msg = leaderboard_card(
            title="ignored",
            entries=dommes,
            summary=summary,
            status=await self.maintenance.get_leaderboard_status(),
        )
        stats_msg = leaderboard_stats_card(summary, dommes)

        await self._upsert_message(
            guild_id=guild_id,
            guild=guild,
            channel=channel,
            message_key="leaderboard",
            leaderboard_type="leaderboard",
            rendered=dommes_msg,
        )
        await self._upsert_message(
            guild_id=guild_id,
            guild=guild,
            channel=channel,
            message_key="leaderboard_stats",
            leaderboard_type="leaderboard_stats",
            rendered=stats_msg,
        )
        return True

    async def get_current_leader(self, guild_id: int):
        leader = await self.leaderboards.get_current_leader(
            guild_id,
            include_test_sends=self.include_test_sends,
            test_gifter_usernames=self.test_gifter_usernames,
            owner_test_user_id=self.owner_test_user_id,
        )
        if leader is None:
            return None
        if leader.total_cents <= 0 and leader.send_count <= 0:
            return None
        return leader

    async def maybe_post_leader_alert(self, guild_id: int, *, previous_leader_user_id: int | None) -> bool:
        if await self.maintenance.is_enabled():
            return False
        current_leader = await self.get_current_leader(guild_id)
        if previous_leader_user_id is None or current_leader is None:
            return False
        if current_leader.user_id == previous_leader_user_id:
            return False

        state_key = f"leader_alert:last_announced:{guild_id}"
        last_announced = await self.bot_state.get_text(state_key)
        if last_announced is not None and int(last_announced) == current_leader.user_id:
            return False

        settings = await self.guild_settings.get(guild_id)
        if settings is None:
            return False

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return False

        channel_id = settings.leaderboard_channel_id or settings.send_track_channel_id
        if channel_id is None:
            log.warning("No leaderboard or send tracking channel configured for leader alert in guild %s.", guild_id)
            return False

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.HTTPException):
                log.warning("Leader alert channel %s is unavailable in guild %s.", channel_id, guild_id)
                return False
        if not isinstance(channel, discord.TextChannel):
            return False

        await channel.send(**leader_alert_card(f"<@{current_leader.user_id}>").send_kwargs())
        await self.bot_state.set_value(state_key, str(current_leader.user_id))
        return True

    async def _upsert_message(
        self,
        *,
        guild_id: int,
        guild: discord.Guild,
        channel: discord.TextChannel,
        message_key: str,
        leaderboard_type: str,
        rendered,
    ) -> None:
        ref = await self.leaderboards.get_message(guild_id, message_key)
        message: discord.Message | None = None
        message_channel: discord.TextChannel | None = channel
        if ref is not None:
            if ref.channel_id != channel.id:
                candidate_channel = guild.get_channel(ref.channel_id)
                if candidate_channel is None:
                    try:
                        candidate_channel = await guild.fetch_channel(ref.channel_id)
                    except (discord.NotFound, discord.HTTPException):
                        candidate_channel = None
                if isinstance(candidate_channel, discord.TextChannel):
                    message_channel = candidate_channel
            try:
                if message_channel is not None:
                    message = await message_channel.fetch_message(ref.message_id)
            except (discord.NotFound, discord.HTTPException, KeyError):
                log.info(
                    "Referenced leaderboard message missing for guild_id=%s key=%s channel_id=%s message_id=%s; creating replacement.",
                    guild_id,
                    message_key,
                    ref.channel_id,
                    ref.message_id,
                )
                message = None
        if message is None:
            if ref is None:
                log.info(
                    "Creating leaderboard message because no ref exists for guild_id=%s key=%s",
                    guild_id,
                    message_key,
                )
            message = await channel.send(**rendered.send_kwargs())
        else:
            log.info(
                "Updating existing leaderboard message_id=%s guild_id=%s key=%s",
                message.id,
                guild_id,
                message_key,
            )
            await message.edit(**rendered.edit_kwargs())
        await self.leaderboards.upsert_message(
            guild_id=guild_id,
            message_key=message_key,
            leaderboard_type=leaderboard_type,
            channel_id=channel.id,
            message_id=message.id,
        )
