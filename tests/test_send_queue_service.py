from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from rob.database.repositories.models import SendRecord
from rob.services.send_queue_service import SendQueueService


def _send() -> SendRecord:
    now = datetime.now(timezone.utc)
    return SendRecord(
        1,
        1,
        None,
        10,
        None,
        20,
        "gifter",
        1099,
        "USD",
        "paypal",
        "manual:paypal",
        "Flowers",
        None,
        None,
        None,
        None,
        False,
        False,
        now,
        now,
        "pending",
        None,
        None,
        None,
        now,
    )


class _FakeMaintenance:
    async def is_enabled(self) -> bool:
        return False

    async def consume_leaderboard_refresh_request(self) -> bool:
        return False


class _FakeSettingsRepo:
    async def get(self, _guild_id: int):
        return SimpleNamespace(send_track_channel_id=123)


class _FakeSends:
    def __init__(self) -> None:
        self.mark_posted_calls: list[int] = []
        self.mark_failed_calls: list[int] = []
        self.released = 0
        self.pending = [_send()]

    async def release_queued_maintenance(self):
        return self.released

    async def fetch_for_status(self, _status: str, *, limit: int = 50):
        del limit
        return list(self.pending)

    async def mark_posted(self, send_id: int, *, message_id: int | None):
        del message_id
        self.mark_posted_calls.append(send_id)

    async def mark_failed(self, send_id: int, *, error: str):
        del error
        self.mark_failed_calls.append(send_id)


class _FakeMessage:
    def __init__(self, message_id: int):
        self.id = message_id


class _FakeChannel:
    async def send(self, **_kwargs):
        return _FakeMessage(555)


class _FakeGuild:
    def __init__(self):
        self.channel = _FakeChannel()

    def get_channel(self, _channel_id: int):
        return self.channel


class _FakeBot:
    def __init__(self):
        self.guild = _FakeGuild()

    def get_guild(self, _guild_id: int):
        return self.guild

    async def wait_until_ready(self):
        return


class _FakeLeaderboard:
    def __init__(self):
        self.refresh_calls: list[int] = []
        self.refresh_all_calls = 0
        self.alert_calls = 0
        self.raise_alert = False

    async def refresh_guild(self, guild_id: int):
        self.refresh_calls.append(guild_id)

    async def refresh_all_guilds(self):
        self.refresh_all_calls += 1

    async def get_current_leader(self, _guild_id: int):
        return SimpleNamespace(user_id=10)

    async def maybe_post_leader_alert(self, _guild_id: int, *, previous_leader_user_id: int | None):
        del previous_leader_user_id
        self.alert_calls += 1
        if self.raise_alert:
            raise RuntimeError("leader alert failed")


class _FakeCounting:
    def __init__(self):
        self.calls = 0

    async def process_send_for_count_rescue(self, _send):
        self.calls += 1
        return False


def test_send_queue_refreshes_after_successful_send_post(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("rob.services.send_queue_service.discord.TextChannel", _FakeChannel)
    sends = _FakeSends()
    leaderboard = _FakeLeaderboard()
    service = SendQueueService(
        bot=_FakeBot(),
        sends=sends,
        guild_settings=_FakeSettingsRepo(),
        maintenance=_FakeMaintenance(),
        leaderboard_service=leaderboard,
        counting_service=_FakeCounting(),
    )

    asyncio.run(service.process_cycle())

    assert sends.mark_posted_calls == [1]
    assert leaderboard.refresh_calls == [1]


def test_send_queue_still_refreshes_if_leader_alert_fails(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("rob.services.send_queue_service.discord.TextChannel", _FakeChannel)
    sends = _FakeSends()
    leaderboard = _FakeLeaderboard()
    leaderboard.raise_alert = True
    service = SendQueueService(
        bot=_FakeBot(),
        sends=sends,
        guild_settings=_FakeSettingsRepo(),
        maintenance=_FakeMaintenance(),
        leaderboard_service=leaderboard,
        counting_service=_FakeCounting(),
    )

    asyncio.run(service.process_cycle())

    assert sends.mark_posted_calls == [1]
    assert leaderboard.refresh_calls == [1]


def test_send_queue_does_not_refresh_for_failed_send_post():
    sends = _FakeSends()
    leaderboard = _FakeLeaderboard()
    service = SendQueueService(
        bot=_FakeBot(),
        sends=sends,
        guild_settings=_FakeSettingsRepo(),
        maintenance=_FakeMaintenance(),
        leaderboard_service=leaderboard,
        counting_service=_FakeCounting(),
    )

    async def _always_fail(_send):
        return False

    service._post_send = _always_fail  # type: ignore[method-assign]
    asyncio.run(service.process_cycle())

    assert leaderboard.refresh_calls == []


def test_send_queue_refreshes_all_leaderboards_once_on_startup():
    sends = _FakeSends()
    leaderboard = _FakeLeaderboard()
    service = SendQueueService(
        bot=_FakeBot(),
        sends=sends,
        guild_settings=_FakeSettingsRepo(),
        maintenance=_FakeMaintenance(),
        leaderboard_service=leaderboard,
        counting_service=_FakeCounting(),
    )

    asyncio.run(service._refresh_leaderboards_on_startup())
    asyncio.run(service._refresh_leaderboards_on_startup())

    assert leaderboard.refresh_all_calls == 1
