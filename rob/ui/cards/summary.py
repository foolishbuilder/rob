from __future__ import annotations

import discord

from rob.ui.render import RenderedMessage, require_components_v2

COLOR_SUMMARY = 0x9B8EC4


def _join_names(names: list[str]) -> str:
    if not names:
        return "No one"
    limited = names[:5]
    if len(names) > 5:
        limited.append("a few others")
    if len(limited) == 1:
        return limited[0]
    return ", ".join(limited[:-1]) + f" and {limited[-1]}"


def summary_card(
    *,
    display_name: str,
    period: str,
    next_period: str,
    send_count: int,
    total_amount: str,
    sender_names: list[str],
) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=1800)
    if send_count > 0:
        body = (
            f"Hey {display_name} 💜\n\n"
            f"Here is a look back at your {period}. Rob counted {send_count} sends coming through. {_join_names(sender_names)} all showed up for you.\n\n"
            f"{total_amount} worth of sends, all logged and taken care of.\n\n"
            f"See you {next_period}. Rob 🤍"
        )
    else:
        body = (
            f"Hey {display_name} 💜\n\n"
            f"Rob is popping in for your {period} check in. Quiet one this time but that is alright. Rob is still here.\n\n"
            f"See you {next_period}. Rob 🤍"
        )
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(body),
            accent_color=COLOR_SUMMARY,
        )
    )
    return RenderedMessage(view=view)
