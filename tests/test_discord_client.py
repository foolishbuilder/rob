from __future__ import annotations

import asyncio
from types import SimpleNamespace

from rob.discord.client import RobBot


class _FakeTree:
    def __init__(self):
        self.clear_calls: list[object] = []
        self.sync_calls: list[object | None] = []

    def clear_commands(self, *, guild=None):
        self.clear_calls.append(guild)

    async def sync(self, *, guild=None):
        self.sync_calls.append(guild)
        return [SimpleNamespace(name="leaderboard")]


def test_single_guild_sync_clears_stale_guild_commands_before_global_sync():
    tree = _FakeTree()
    fake_bot = SimpleNamespace(tree=tree)

    asyncio.run(RobBot._sync_application_commands(fake_bot, [123456789]))

    assert len(tree.clear_calls) == 1
    assert len(tree.sync_calls) == 2
    assert tree.sync_calls[0] is tree.clear_calls[0]
    assert tree.sync_calls[1] is None


def test_multi_guild_sync_keeps_global_only():
    tree = _FakeTree()
    fake_bot = SimpleNamespace(tree=tree)

    asyncio.run(RobBot._sync_application_commands(fake_bot, [1, 2]))

    assert tree.clear_calls == []
    assert tree.sync_calls == [None]
