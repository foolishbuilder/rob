from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from rob.discord.guilds import is_test_guild
from rob.ui.cards.errors import error_card
from rob.ui.cards.mode_selection import ModeSelectionView, mode_selection_card

if TYPE_CHECKING:
    from rob.discord.client import RobBot


class SettingsCog(commands.Cog):
    settings_group = app_commands.Group(name="settings", description="Manage your Rob settings.")

    def __init__(self, bot: RobBot) -> None:
        self.bot = bot

    @settings_group.command(name="mode", description="Update your send notification mode.")
    async def settings_mode(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(**error_card("This command can only be used in a server.").send_kwargs(), ephemeral=True)
            return
        if not is_test_guild(interaction.guild.id):
            await interaction.response.send_message(**error_card("This command is currently enabled in the test guild only.").send_kwargs(), ephemeral=True)
            return
        domme = await self.bot.dommes_repo.get_by_user_id(interaction.guild.id, interaction.user.id)
        if domme is None:
            await interaction.response.send_message(**error_card("Only registered Dom/mes can use this setting.").send_kwargs(), ephemeral=True)
            return
        await interaction.response.send_message(
            **mode_selection_card(view=ModeSelectionView(self.bot, guild_id=interaction.guild.id, discord_user_id=interaction.user.id)).send_kwargs(),
            ephemeral=True,
        )

    @settings_group.command(name="summary", description="Update your private summary cadence.")
    @app_commands.choices(
        cadence=[
            app_commands.Choice(name="weekly", value="weekly"),
            app_commands.Choice(name="fortnightly", value="fortnightly"),
            app_commands.Choice(name="monthly", value="monthly"),
        ]
    )
    async def settings_summary(
        self,
        interaction: discord.Interaction,
        cadence: app_commands.Choice[str],
    ) -> None:
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(**error_card("This command can only be used in a server.").send_kwargs(), ephemeral=True)
            return
        if not is_test_guild(interaction.guild.id):
            await interaction.response.send_message(**error_card("This command is currently enabled in the test guild only.").send_kwargs(), ephemeral=True)
            return
        domme = await self.bot.dommes_repo.get_by_user_id(interaction.guild.id, interaction.user.id)
        if domme is None:
            await interaction.response.send_message(**error_card("Only registered Dom/mes can use this setting.").send_kwargs(), ephemeral=True)
            return
        if domme.notification_mode not in {"private", "private_leaderboard"}:
            await interaction.response.send_message(
                **error_card("Summary cadence is only used in private modes. Set your mode to private first.").send_kwargs(),
                ephemeral=True,
            )
            return
        await self.bot.dommes_repo.set_summary_cadence(
            guild_id=interaction.guild.id,
            discord_user_id=interaction.user.id,
            summary_cadence=cadence.value,
        )
        await interaction.response.send_message(f"Saved. Rob will send summaries {cadence.value}.", ephemeral=True)
