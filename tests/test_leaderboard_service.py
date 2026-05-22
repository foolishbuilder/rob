from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from rob.database.repositories.models import LeaderboardEntry, LeaderboardSummary
from rob.services.leaderboard_service import LeaderboardService


class _FakeMessage:
    def __init__(self, message_id: int):
        self.id = message_id
        self.edits: list[dict] = []

    async def edit(self, **kwargs):
        self.edits.append(kwargs)


class _FakeChannel:
    def __init__(self):
        self.id = 999
        self._messages: dict[int, _FakeMessage] = {}
        self.sends: list[dict] = []

    async def fetch_message(self, message_id: int):
        return self._messages[message_id]

    async def send(self, **kwargs):
        self.sends.append(kwargs)
        message = _FakeMessage(len(self.sends))
        self._messages[message.id] = message
        return message


class _FakeGuild:
    def __init__(self, channel):
        self._channel = channel

    def get_channel(self, _):
        return self._channel


class _FakeBot:
    def __init__(self, guild):
        self._guild = guild

    def get_guild(self, _):
        return self._guild


class _FakeSettingsRepo:
    async def get(self, _):
        return SimpleNamespace(leaderboard_channel_id=123)

    async def list_guild_ids(self):
        return [1]


class _FakeLeaderboardsRepo:
    def __init__(self):
        self.refs = {}
        self.upserts = []

    async def get_summary(self, _):
        return LeaderboardSummary(total_cents=1000, send_count=2, domme_count=1, sub_count=1)

    async def get_top_dommes(self, _):
        return [LeaderboardEntry(label='@Domme', user_id=1, total_cents=1000, send_count=2)]

    async def get_top_subs(self, _):
        return [LeaderboardEntry(label='@Sub', user_id=2, total_cents=1000, send_count=2)]

    async def get_message(self, guild_id, message_key):
        return self.refs.get((guild_id, message_key))

    async def upsert_message(self, **kwargs):
        self.upserts.append(kwargs)
        self.refs[(kwargs['guild_id'], kwargs['message_key'])] = SimpleNamespace(message_id=kwargs['message_id'])


def test_refresh_posts_main_and_stats_messages_not_sub_leaderboard(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("rob.services.leaderboard_service.discord.TextChannel", _FakeChannel)
    channel = _FakeChannel()
    guild = _FakeGuild(channel)
    service = LeaderboardService(
        bot=_FakeBot(guild),
        guild_settings=_FakeSettingsRepo(),
        leaderboards=_FakeLeaderboardsRepo(),
    )

    ok = asyncio.run(service.refresh_guild(1))
    assert ok is True
    assert len(channel.sends) == 2

    first_text = "\n".join(str(getattr(x, "content", "")) for x in channel.sends[0]["view"].children[0].children)
    second_text = "\n".join(str(getattr(x, "content", "")) for x in channel.sends[1]["view"].children[0].children)
    assert 'Thy Send Leaderboard' in first_text
    assert 'Thy Send Leaderboard | Stats' in second_text


def test_refresh_uses_new_message_keys_for_upsert(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("rob.services.leaderboard_service.discord.TextChannel", _FakeChannel)
    channel = _FakeChannel()
    guild = _FakeGuild(channel)
    repo = _FakeLeaderboardsRepo()
    service = LeaderboardService(
        bot=_FakeBot(guild),
        guild_settings=_FakeSettingsRepo(),
        leaderboards=repo,
    )

    asyncio.run(service.refresh_guild(1))

    keys = [u['message_key'] for u in repo.upserts]
    assert keys == ['leaderboard', 'leaderboard_stats']
