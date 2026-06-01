from __future__ import annotations

from dataclasses import dataclass

import discord

from rob.ui.components import make_card, render
from rob.ui.render import CardSection, RenderedMessage, require_components_v2
from rob.ui.theme import COLOR_LEADERBOARD
from rob.utils.money import format_money_from_cents, format_money_with_currency_name


@dataclass(frozen=True)
class DommeStatsCardData:
    display_name: str
    rank: int | None
    total_cents: int
    send_count: int
    top_sub_label: str
    latest_item_name: str | None
    latest_amount_cents: int | None
    latest_currency: str | None
    latest_item_image_url: str | None


@dataclass(frozen=True)
class SubStatsCardData:
    display_name: str
    total_cents: int
    send_count: int
    top_domme_label: str
    latest_item_name: str | None
    latest_amount_cents: int | None
    latest_currency: str | None
    latest_item_image_url: str | None
    latest_domme_label: str | None


def _rank_label(rank: int | None) -> str:
    if rank is None:
        return "Not ranked yet"
    if rank == 1:
        return "👑 #1"
    return f"#{rank}"


def _latest_send_details_section(
    *,
    title: str,
    body: str,
    image_url: str | None,
) -> discord.ui.Container:
    children: list[discord.ui.Item] = [
        discord.ui.TextDisplay(f"### {title}"),
        discord.ui.Separator(),
    ]
    if image_url:
        children.append(
            discord.ui.Section(
                discord.ui.TextDisplay(body),
                accessory=discord.ui.Thumbnail(media=image_url),
            )
        )
    else:
        children.append(discord.ui.TextDisplay(body))
    return discord.ui.Container(*children, accent_color=COLOR_LEADERBOARD)


def leaderboard_personal_stats_card(
    *,
    domme_stats: DommeStatsCardData | None,
    sub_stats: SubStatsCardData | None,
    unregistered_text: str,
) -> RenderedMessage:
    require_components_v2()

    if domme_stats is None and sub_stats is None:
        return render(
            make_card(
                title="You're not on the leaderboard just yet",
                body=unregistered_text,
                color=COLOR_LEADERBOARD,
                variant="dashboard",
                footer="Run /register to get started.",
            )
        )

    view = discord.ui.LayoutView(timeout=1800)

    if domme_stats is not None:
        domme_msg = render(
            make_card(
                title=f"{domme_stats.display_name}'s Send Stats | Dom/me",
                body="Your Dom/me leaderboard stats at a glance.",
                color=COLOR_LEADERBOARD,
                variant="dashboard",
                sections=[
                    CardSection(title="Rank", text=_rank_label(domme_stats.rank), inline=True),
                    CardSection(
                        title="Sends",
                        text=f"{domme_stats.send_count} · {format_money_from_cents(domme_stats.total_cents)}",
                        inline=True,
                    ),
                    CardSection(title="Top Sub", text=domme_stats.top_sub_label, inline=True),
                ],
            )
        )
        # Transfer container from rendered card to our combined view
        if domme_msg.view and hasattr(domme_msg.view, "children"):
            for child in domme_msg.view.children:
                view.add_item(child)

        if domme_stats.latest_amount_cents is None:
            latest_body = "No sends tracked yet."
        else:
            latest_body = (
                f"**{domme_stats.latest_item_name or 'Mystery send'}**\n"
                f"{format_money_with_currency_name(domme_stats.latest_amount_cents, domme_stats.latest_currency or 'USD')}"
            )
        view.add_item(
            _latest_send_details_section(
                title="Latest Send Details",
                body=latest_body,
                image_url=domme_stats.latest_item_image_url,
            )
        )

    if sub_stats is not None:
        sub_msg = render(
            make_card(
                title=f"{sub_stats.display_name}'s Send Stats | Sub",
                body="Your Sub send stats at a glance.",
                color=COLOR_LEADERBOARD,
                variant="dashboard",
                sections=[
                    CardSection(
                        title="Total Sent",
                        text=format_money_from_cents(sub_stats.total_cents),
                        inline=True,
                    ),
                    CardSection(title="Sends", text=str(sub_stats.send_count), inline=True),
                    CardSection(title="Top Dom/me", text=sub_stats.top_domme_label, inline=True),
                ],
            )
        )
        if sub_msg.view and hasattr(sub_msg.view, "children"):
            for child in sub_msg.view.children:
                view.add_item(child)

        if sub_stats.latest_amount_cents is None:
            latest_sub_body = "No sends tracked yet."
        else:
            latest_sub_body = (
                f"**{sub_stats.latest_item_name or 'Mystery send'}**\n"
                f"{format_money_with_currency_name(sub_stats.latest_amount_cents, sub_stats.latest_currency or 'USD')}"
            )
            if sub_stats.latest_domme_label:
                latest_sub_body += f"\nTo: {sub_stats.latest_domme_label}"
        view.add_item(
            _latest_send_details_section(
                title="Latest Send To Dom/me",
                body=latest_sub_body,
                image_url=sub_stats.latest_item_image_url,
            )
        )

    return RenderedMessage(view=view)
