from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from rob.ui.render import RenderedMessage, require_components_v2
from rob.ui.theme import COLOR_PRIMARY

if TYPE_CHECKING:
    from rob.discord.client import RobBot


def mode_selection_card(*, view: discord.ui.LayoutView | None = None) -> RenderedMessage:
    require_components_v2()
    render_view = view or discord.ui.LayoutView(timeout=1800)
    render_view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("## How would you like your sends shared?"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "Rob tracks three modes. Pick the one that feels right.\n\n"
                "📢 Public\n"
                "Send notifications posted publicly.\n"
                "You appear on the leaderboard.\n\n"
                "🔒 Private\n"
                "No public notifications. Hidden from the leaderboard. Rob sends you a personal summary instead.\n\n"
                "🔒📊 Private + Leaderboard\n"
                "No public notifications but you still appear on the leaderboard. Personal summary included.\n\n"
                "-# You can change this later with\n"
                "-# /settings"
            ),
            accent_color=COLOR_PRIMARY,
        )
    )
    return RenderedMessage(view=render_view)


class _ModeButton(discord.ui.Button):
    def __init__(self, *, label: str, mode: str, bot: RobBot, guild_id: int, discord_user_id: int) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.mode = mode
        self.bot = bot
        self.guild_id = guild_id
        self.discord_user_id = discord_user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user is None or interaction.user.id != self.discord_user_id:
            await interaction.response.send_message("This setup flow belongs to someone else.", ephemeral=True)
            return
        await self.bot.dommes_repo.set_notification_mode(
            guild_id=self.guild_id,
            discord_user_id=self.discord_user_id,
            notification_mode=self.mode,
        )
        await interaction.response.send_message("Saved. Rob updated your mode.", ephemeral=True)


class ModeSelectionView(discord.ui.LayoutView):
    def __init__(self, bot: RobBot, *, guild_id: int, discord_user_id: int) -> None:
        super().__init__(timeout=1800)
        self.add_item(_ModeButton(label="Public", mode="public", bot=bot, guild_id=guild_id, discord_user_id=discord_user_id))
        self.add_item(_ModeButton(label="Private", mode="private", bot=bot, guild_id=guild_id, discord_user_id=discord_user_id))
        self.add_item(
            _ModeButton(
                label="Private + LB",
                mode="private_leaderboard",
                bot=bot,
                guild_id=guild_id,
                discord_user_id=discord_user_id,
            )
        )
