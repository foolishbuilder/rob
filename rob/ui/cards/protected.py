from __future__ import annotations

import discord

from rob.ui.components import make_card, render
from rob.ui.render import RenderedMessage
from rob.ui.theme import COLOR_WHITE


def protected_member_card(
    *,
    user_id: int,
    display_name: str | None,
    view: discord.ui.LayoutView | None = None,
) -> RenderedMessage:
    """Memorial card announcing that a member's account is protected.

    The body shows the member's mention (the sender should pass
    ``allowed_mentions`` so it does not ping the account). ``view`` is the
    LayoutView the caller renders into and then attaches the GoFundMe link
    button to.
    """

    name = (display_name or "This member").strip() or "This member"
    body = (
        "In loving memory. 🤍\n\n"
        f"Rob will always watch over <@{user_id}>'s account here in VIB and "
        "safeguard it from any change. Their place in this community is permanent."
    )
    footer = (
        f"{name} is shielded from the inactivity system and every other automation "
        "that could remove them from the server.\n"
        f"-# In every server backup, {name}'s account is preserved and prioritised above all else."
    )
    return render(
        make_card(
            title="🪽 Protected Member 🪽",
            body=body,
            color=COLOR_WHITE,
            footer=footer,
            variant="default",
        ),
        view=view,
    )
