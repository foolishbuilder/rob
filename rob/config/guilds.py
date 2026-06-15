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


__all__ = [
    "MAIN_GUILD_ID",
    "TEST_GUILD_ID",
    "OWNER_USER_ID",
    "is_test_guild",
    "is_main_guild",
]
