from __future__ import annotations

MAIN_GUILD_ID = 1485460387355820034
TEST_GUILD_ID = 1506597978251591813


def is_test_guild(guild_id: int) -> bool:
    return guild_id == TEST_GUILD_ID
