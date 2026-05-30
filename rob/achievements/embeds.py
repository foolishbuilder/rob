from __future__ import annotations

import math

import discord

from rob.achievements.definitions import (
    ACHIEVEMENTS_BY_KEY,
    ENABLED_ACHIEVEMENTS,
    AchievementDefinition,
)
from rob.ui.render import RenderedMessage, require_components_v2
from rob.ui.theme import COLOR_ROB_PURPLE, COLOR_SUCCESS

_ENTRIES_PER_PAGE = 15


def _achievement_field(
    achievement: AchievementDefinition,
    *,
    unlocked: bool,
) -> tuple[str, str]:
    if not unlocked and achievement.hidden:
        return ("Secret Achievement", "???")
    return (achievement.title, achievement.description)


def achievement_unlocked_card(
    achievement: AchievementDefinition,
    *,
    unlocked_by_display_name: str | None = None,
    include_meta_line: bool = False,
) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=1800)
    children: list[discord.ui.Item] = [
        discord.ui.TextDisplay(f"### {achievement.title}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(achievement.description),
    ]
    if include_meta_line:
        children.append(discord.ui.Separator())
        children.append(
            discord.ui.TextDisplay(
                f"-# Key: {achievement.key} | Category: {achievement.category} | Rarity: {achievement.rarity}"
            )
        )
    if unlocked_by_display_name:
        children.append(discord.ui.Separator())
        children.append(discord.ui.TextDisplay(f"-# Unlocked by {unlocked_by_display_name}"))
    view.add_item(discord.ui.Container(*children, accent_color=COLOR_SUCCESS))
    return RenderedMessage(view=view)


def achievements_overview_cards(
    *,
    display_name: str,
    unlocked_keys: set[str],
    for_self: bool,
    newly_unlocked_count: int | None = None,
) -> list[RenderedMessage]:
    known_unlocked = {
        key
        for key in unlocked_keys
        if key in ACHIEVEMENTS_BY_KEY and key in {achievement.key for achievement in ENABLED_ACHIEVEMENTS}
    }
    page_count = max(1, math.ceil(len(ENABLED_ACHIEVEMENTS) / _ENTRIES_PER_PAGE))
    summary_line = f"Achievements unlocked (total): {len(known_unlocked)}/{len(ENABLED_ACHIEVEMENTS)}"
    if newly_unlocked_count and newly_unlocked_count > 0:
        summary_line = f"{summary_line} +{newly_unlocked_count}"

    cards: list[RenderedMessage] = []
    for index in range(page_count):
        start = index * _ENTRIES_PER_PAGE
        page_achievements = ENABLED_ACHIEVEMENTS[start : start + _ENTRIES_PER_PAGE]

        embed = discord.Embed(
            title="Rob Achievements",
            description=summary_line,
            colour=COLOR_ROB_PURPLE,
        )
        embed.set_author(name=display_name if not for_self else f"{display_name}'s catalogue")
        embed.set_footer(text=f"Page {index + 1}/{page_count}")

        for achievement in page_achievements:
            title, description = _achievement_field(
                achievement,
                unlocked=achievement.key in known_unlocked,
            )
            embed.add_field(name=title, value=description, inline=True)

        cards.append(RenderedMessage(embeds=[embed], view=discord.ui.View(timeout=1800), mode="embed"))

    return cards
