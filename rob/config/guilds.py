"""Central guild ID constants and gating helpers.

All new functionality that is scoped to the test guild ONLY should consult
``is_test_guild`` before mutating shared bot state, sending DMs, etc.

Outside of ``TEST_GUILD_ID`` the existing main-server behavior is preserved.
"""

from __future__ import annotations

MAIN_GUILD_ID: int = 1485460387355820034
TEST_GUILD_ID: int = 1506597978251591813

# The bot operator's Discord *user* id (the human who runs Rob). This is who
# /report submissions are DM'd to. Intentionally NOT the Discord application
# owner from application_info(), which can be a team account or have DMs closed.
OWNER_USER_ID: int = 1299308718009356289

# "DO NOT TOUCH" users. Rob's member-lifecycle automations (the inactivity
# system: Active/Inactive role swaps, inactivity DMs, and auto-kicks) must never
# act on these accounts; instead they are kept Active and left in place. Seeded
# with a deceased member whose account is preserved as a memorial.
PROTECTED_USER_IDS: frozenset[int] = frozenset(
    {
        1455563825393832095,
    }
)


def is_test_guild(guild_id: int | None) -> bool:
    """Return ``True`` when ``guild_id`` matches the test guild.

    ``None`` (and any other non-matching guild id) returns ``False`` so that
    callers can safely use this as the only gate for test-server-only paths.
    """

    if guild_id is None:
        return False
    return int(guild_id) == TEST_GUILD_ID


def is_main_guild(guild_id: int | None) -> bool:
    """Return ``True`` when ``guild_id`` matches the production main guild."""

    if guild_id is None:
        return False
    return int(guild_id) == MAIN_GUILD_ID


def is_new_system_guild(guild_id: int | None) -> bool:
    """Guilds where Rob's newer systems are live (main + test): the Dom/me
    onboarding + preferences + leaderboard-access system, and the activity /
    inactive-role + hourly server-backup systems. Each was test-guild-only during
    development and promoted to the main guild here."""
    if guild_id is None:
        return False
    return is_main_guild(guild_id) or is_test_guild(guild_id)


def is_protected_user(user_id: int | None) -> bool:
    """Return ``True`` for "DO NOT TOUCH" accounts that Rob's member-lifecycle
    automations must never act on (never kicked, never marked inactive)."""

    if user_id is None:
        return False
    return int(user_id) in PROTECTED_USER_IDS


__all__ = [
    "MAIN_GUILD_ID",
    "TEST_GUILD_ID",
    "OWNER_USER_ID",
    "PROTECTED_USER_IDS",
    "is_test_guild",
    "is_main_guild",
    "is_new_system_guild",
    "is_protected_user",
]
