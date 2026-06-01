from __future__ import annotations

import discord


ROB_NAVY = discord.Colour.from_rgb(29, 53, 87)
ROB_SKY = discord.Colour.from_rgb(69, 123, 157)
ROB_GOLD = discord.Colour.from_rgb(230, 182, 70)
ROB_GREEN = discord.Colour.from_rgb(76, 175, 80)
ROB_RED = discord.Colour.from_rgb(198, 40, 40)
ROB_STONE = discord.Colour.from_rgb(108, 117, 125)
ROB_PINK = discord.Colour.from_rgb(214, 93, 177)
COLOR_ROB_PURPLE = discord.Colour(0x7B61FF)

COLOR_INFO = ROB_SKY
COLOR_SUCCESS = ROB_GREEN
COLOR_WARNING = ROB_GOLD
COLOR_DANGER = ROB_RED
COLOR_NEUTRAL = ROB_STONE
COLOR_PRIMARY = ROB_NAVY
COLOR_SEND = COLOR_ROB_PURPLE
COLOR_LEADERBOARD = COLOR_ROB_PURPLE
COLOR_LEADER_ALERT = COLOR_ROB_PURPLE

# Variant-to-color mapping: provides a default accent color per variant
VARIANT_COLORS: dict[str, discord.Colour] = {
    "default": COLOR_INFO,
    "success": COLOR_SUCCESS,
    "error": COLOR_DANGER,
    "warning": COLOR_WARNING,
    "danger": COLOR_DANGER,
    "setup": COLOR_PRIMARY,
    "workflow": COLOR_PRIMARY,
    "leaderboard": COLOR_LEADERBOARD,
    "send": COLOR_SEND,
    "celebration": COLOR_SEND,
    "counting": COLOR_INFO,
    "status": COLOR_SUCCESS,
    "dashboard": COLOR_LEADERBOARD,
}


def color_for_variant(variant: str) -> discord.Colour:
    """Return the default accent color for a given card variant."""
    return VARIANT_COLORS.get(variant, COLOR_INFO)
