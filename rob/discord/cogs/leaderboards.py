from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from rob.ui.cards.errors import error_card
from rob.ui.cards.stats import (
    DommeStatsCardData,
    SubStatsCardData,
    leaderboard_personal_stats_card,
)

if TYPE_CHECKING:
    from rob.discord.client import RobBot


class LeaderboardsCog(commands.Cog):
    def __init__(self, bot: RobBot) -> None:
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show your personal send stats.")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(**error_card("This command can only be used in a server.").send_kwargs(), ephemeral=True)
            return

        include_test_sends = self.bot.settings.throne_parse_test_sends_as_real_sends
        usernames = self.bot.settings.throne_test_gifter_usernames
        owner_test_user_id = self.bot.settings.throne_test_send_leaderboard_owner_user_id
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        domme = await self.bot.dommes_repo.get_by_user_id(guild_id, user_id)
        sub = await self.bot.subs_repo.get_by_user_id(guild_id, user_id)

        domme_stats_data: DommeStatsCardData | None = None
        if domme is not None:
            stats = await self.bot.leaderboards_repo.get_domme_stats(
                guild_id,
                domme_user_id=user_id,
                include_test_sends=include_test_sends,
                test_gifter_usernames=usernames,
                owner_test_user_id=owner_test_user_id,
            )
            rank = await self.bot.leaderboards_repo.get_domme_rank(
                guild_id,
                domme_user_id=user_id,
                include_test_sends=include_test_sends,
                test_gifter_usernames=usernames,
                owner_test_user_id=owner_test_user_id,
            )
            latest = await self.bot.leaderboards_repo.get_domme_latest_send(
                guild_id,
                domme_user_id=user_id,
                include_test_sends=include_test_sends,
                test_gifter_usernames=usernames,
                owner_test_user_id=owner_test_user_id,
            )
            top_sub = await self.bot.leaderboards_repo.get_domme_top_sending_sub(
                guild_id,
                domme_user_id=user_id,
                include_test_sends=include_test_sends,
                test_gifter_usernames=usernames,
                owner_test_user_id=owner_test_user_id,
            )
            top_sub_label = "User not in server or has not connected account"
            if top_sub is not None and top_sub.user_id is not None:
                top_sub_label = f"<@{top_sub.user_id}>"
            domme_stats_data = DommeStatsCardData(
                display_name=interaction.user.display_name,
                rank=rank,
                total_cents=stats.total_cents,
                send_count=stats.send_count,
                top_sub_label=top_sub_label,
                latest_item_name=latest.item_name if latest is not None else None,
                latest_amount_cents=latest.amount_cents if latest is not None else None,
                latest_currency=latest.currency if latest is not None else None,
                latest_item_image_url=latest.item_image_url if latest is not None else None,
            )

        sub_stats_data: SubStatsCardData | None = None
        if sub is not None:
            stats = await self.bot.leaderboards_repo.get_sub_stats(
                guild_id,
                sub_user_id=user_id,
                include_test_sends=include_test_sends,
                test_gifter_usernames=usernames,
                owner_test_user_id=owner_test_user_id,
            )
            latest = await self.bot.leaderboards_repo.get_sub_latest_send(
                guild_id,
                sub_user_id=user_id,
                include_test_sends=include_test_sends,
                test_gifter_usernames=usernames,
                owner_test_user_id=owner_test_user_id,
            )
            top_domme = await self.bot.leaderboards_repo.get_sub_top_domme(
                guild_id,
                sub_user_id=user_id,
                include_test_sends=include_test_sends,
                test_gifter_usernames=usernames,
                owner_test_user_id=owner_test_user_id,
            )

            def _domme_display_name(domme_user_id: int | None) -> str:
                if domme_user_id is None:
                    return "User not in server or has not connected account"
                member = interaction.guild.get_member(domme_user_id)
                if member is not None:
                    return member.display_name
                return "User not in server or has not connected account"

            sub_stats_data = SubStatsCardData(
                display_name=interaction.user.display_name,
                total_cents=stats.total_cents,
                send_count=stats.send_count,
                top_domme_label=_domme_display_name(top_domme.user_id if top_domme is not None else None),
                latest_item_name=latest.item_name if latest is not None else None,
                latest_amount_cents=latest.amount_cents if latest is not None else None,
                latest_currency=latest.currency if latest is not None else None,
                latest_item_image_url=latest.item_image_url if latest is not None else None,
                latest_domme_label=_domme_display_name(latest.domme_user_id if latest is not None else None),
            )

        rendered = leaderboard_personal_stats_card(
            domme_stats=domme_stats_data,
            sub_stats=sub_stats_data,
            unregistered_text=(
                "Rob could not find you on either leaderboard yet.\n\n"
                "Dom/mes: run /register domme in this server.\n"
                "Subs: run /register sub in this server."
            ),
        )
        await interaction.response.send_message(**rendered.send_kwargs(), ephemeral=True)
