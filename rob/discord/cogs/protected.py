from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from rob.ui.cards.protected import protected_member_card
from rob.ui.render import add_card_actions

if TYPE_CHECKING:
    from rob.discord.client import RobBot

log = logging.getLogger(__name__)

# The memorial account this command celebrates (also in PROTECTED_USER_IDS).
_MEMORIAL_USER_ID = 1455563825393832095
_GOFUNDME_URL = "https://www.gofundme.com/f/help-lay-alyssa-rae-butler-to-rest"


class ProtectedCog(commands.Cog):
    """`!protected` posts the memorial card for the protected account."""

    def __init__(self, bot: "RobBot") -> None:
        self.bot = bot

    async def _resolve_display_name(self, ctx: commands.Context) -> str | None:
        if ctx.guild is not None:
            member = ctx.guild.get_member(_MEMORIAL_USER_ID)
            if member is not None:
                return member.display_name
        user = self.bot.get_user(_MEMORIAL_USER_ID)
        if user is None:
            try:
                user = await self.bot.fetch_user(_MEMORIAL_USER_ID)
            except discord.HTTPException:
                return None
        return user.display_name if user is not None else None

    @commands.command(name="protected")
    async def protected(self, ctx: commands.Context) -> None:
        display_name = await self._resolve_display_name(ctx)
        view = discord.ui.LayoutView(timeout=None)
        rendered = protected_member_card(
            user_id=_MEMORIAL_USER_ID,
            display_name=display_name,
            view=view,
        )
        add_card_actions(
            view,
            discord.ui.Button(
                label="Help Lay Alyssa Rae to Rest",
                url=_GOFUNDME_URL,
                style=discord.ButtonStyle.link,
            ),
        )
        await ctx.reply(
            **rendered.send_kwargs(),
            mention_author=False,
            # Render the member's name without pinging the account.
            allowed_mentions=discord.AllowedMentions.none(),
        )
