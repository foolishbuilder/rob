from __future__ import annotations

import discord

from rob.database.repositories.models import SendRecord
from rob.ui.render import RenderedMessage, require_components_v2
from rob.ui.theme import COLOR_SEND
from rob.utils.money import format_money_from_cents


def _sub_display(sub_label: str | None) -> str:
    if not sub_label:
        return "The Flying Dutchman"
    if "<@" in sub_label or sub_label.startswith("@"):
        return sub_label
    return f"{sub_label} with no nickname claimed"


def send_card(*, send: SendRecord, domme_label: str, sub_label: str | None, rank: int | None = None):
    del rank
    require_components_v2()
    view = discord.ui.LayoutView(timeout=1800)
    body = (
        f"**Sub:** {_sub_display(sub_label)}\n\n"
        f"**Amount:** {format_money_from_cents(send.amount_cents)} ({send.currency})\n\n"
        f"**Item:** {send.item_name or 'Mystery send'}"
    )
    children = [
        discord.ui.TextDisplay(f"## 💸 New Send to {domme_label}! 💸"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(body),
    ]
    view.add_item(discord.ui.Container(*children, accent_color=COLOR_SEND))
    return RenderedMessage(view=view)
