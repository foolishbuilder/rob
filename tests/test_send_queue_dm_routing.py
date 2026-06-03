"""Test-guild-only DM routing for send-queue posts."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from rob.config.guilds import TEST_GUILD_ID
from rob.services.send_queue_service import SendQueueService


class _FakeMaintenance:
    async def is_enabled(self) -> bool:
        return False


class _FakeSettingsRepo:
    async def get(self, _guild_id):
        return SimpleNamespace(send_track_channel_id=12345)


class _FakeSends:
    def __init__(self):
        self.mark_posted_calls: list[tuple[int, int | None]] = []
        self.mark_failed_calls: list[tuple[int, str]] = []

    async def mark_posted(self, send_id, *, message_id):
        self.mark_posted_calls.append((send_id, message_id))

    async def mark_failed(self, send_id, *, error):
        self.mark_failed_calls.append((send_id, error))


class _FakeDommes:
    def __init__(self, domme):
        self._domme = domme

    async def get_by_user_id(self, _guild_id, _user_id):
        return self._domme


class _FakeBot:
    def __init__(self, user):
        self._user = user

    def get_user(self, _user_id):
        return self._user

    async def fetch_user(self, _user_id):
        return self._user

    def get_guild(self, _guild_id):
        return None


def _send(guild_id=TEST_GUILD_ID):
    return SimpleNamespace(
        id=42,
        guild_id=guild_id,
        domme_id=1,
        domme_user_id=10,
        sub_name="someone",
        sub_id=None,
        sub_user_id=None,
        amount_cents=500,
        currency="USD",
        method="throne",
        source="throne",
        item_name=None,
        item_image_url=None,
        external_id=None,
        event_id=None,
        fallback_event_hash=None,
        is_private=False,
        seeded=False,
        sent_at=None,
        received_at=None,
        status="pending",
        discord_posted_at=None,
        discord_message_id=None,
        discord_post_error=None,
        created_at=None,
        is_test_send=False,
        stored_public_send_id=None,
        original_amount_cents=None,
        original_currency=None,
    )


def _service(*, dommes, bot):
    return SendQueueService(
        bot=bot,
        sends=_FakeSends(),
        guild_settings=_FakeSettingsRepo(),
        maintenance=_FakeMaintenance(),
        leaderboard_service=SimpleNamespace(),
        counting_service=SimpleNamespace(),
        dommes=dommes,
    )


def test_test_guild_send_dms_user_and_marks_posted():
    user = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=999)))
    domme = SimpleNamespace(
        send_notifications_enabled=True,
        notifications_snoozed_until=None,
    )
    service = _service(dommes=_FakeDommes(domme), bot=_FakeBot(user))

    result = asyncio.run(service._post_send_via_dm(_send()))

    assert result is True
    user.send.assert_awaited_once()
    assert service.sends.mark_posted_calls == [(42, 999)]


def test_test_guild_send_skipped_when_notifications_disabled():
    user = SimpleNamespace(send=AsyncMock())
    domme = SimpleNamespace(
        send_notifications_enabled=False,
        notifications_snoozed_until=None,
    )
    service = _service(dommes=_FakeDommes(domme), bot=_FakeBot(user))

    result = asyncio.run(service._post_send_via_dm(_send()))

    assert result is True
    user.send.assert_not_called()
    assert service.sends.mark_posted_calls == [(42, None)]


def test_test_guild_send_skipped_when_snoozed():
    user = SimpleNamespace(send=AsyncMock())
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    domme = SimpleNamespace(
        send_notifications_enabled=True,
        notifications_snoozed_until=future,
    )
    service = _service(dommes=_FakeDommes(domme), bot=_FakeBot(user))

    result = asyncio.run(service._post_send_via_dm(_send()))

    assert result is True
    user.send.assert_not_called()
    assert service.sends.mark_posted_calls == [(42, None)]


def test_test_guild_send_marks_posted_on_dm_forbidden():
    user = SimpleNamespace(
        send=AsyncMock(
            side_effect=discord.Forbidden(SimpleNamespace(status=403, reason=""), "blocked")
        )
    )
    domme = SimpleNamespace(
        send_notifications_enabled=True,
        notifications_snoozed_until=None,
    )
    service = _service(dommes=_FakeDommes(domme), bot=_FakeBot(user))

    result = asyncio.run(service._post_send_via_dm(_send()))

    assert result is True
    assert service.sends.mark_posted_calls == [(42, None)]
    assert service.sends.mark_failed_calls == []


def test_post_send_routes_test_guild_to_dm_and_skips_leader_alert(monkeypatch):
    """``_post_send`` must call ``_post_send_via_dm`` for test guild and
    must NOT call ``maybe_post_leader_alert``."""

    leaderboard = SimpleNamespace(
        get_current_leader=AsyncMock(),
        maybe_post_leader_alert=AsyncMock(),
    )
    service = SendQueueService(
        bot=_FakeBot(SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=1)))),
        sends=_FakeSends(),
        guild_settings=_FakeSettingsRepo(),
        maintenance=_FakeMaintenance(),
        leaderboard_service=leaderboard,
        counting_service=SimpleNamespace(),
        dommes=_FakeDommes(
            SimpleNamespace(
                send_notifications_enabled=True,
                notifications_snoozed_until=None,
            )
        ),
    )

    dm_called = []

    async def _stub_dm(send):
        dm_called.append(send.id)
        return True

    monkeypatch.setattr(service, "_post_send_via_dm", _stub_dm)

    result = asyncio.run(service._post_send(_send()))

    assert result is True
    assert dm_called == [42]
    leaderboard.maybe_post_leader_alert.assert_not_called()
    leaderboard.get_current_leader.assert_not_called()


@pytest.mark.parametrize("guild_id", [1485460387355820034, 999_999_999_999_999_999])
def test_post_send_non_test_guild_does_not_call_dm(monkeypatch, guild_id):
    """For non-test guilds the DM branch must not be entered."""

    leaderboard = SimpleNamespace(
        get_current_leader=AsyncMock(return_value=None),
        maybe_post_leader_alert=AsyncMock(),
    )

    class _NoGuildBot(_FakeBot):
        def get_guild(self, _guild_id):
            return None

    service = SendQueueService(
        bot=_NoGuildBot(SimpleNamespace()),
        sends=_FakeSends(),
        guild_settings=_FakeSettingsRepo(),
        maintenance=_FakeMaintenance(),
        leaderboard_service=leaderboard,
        counting_service=SimpleNamespace(),
        dommes=None,
    )

    dm_called = []

    async def _stub_dm(send):
        dm_called.append(send.id)
        return True

    monkeypatch.setattr(service, "_post_send_via_dm", _stub_dm)

    # We expect _post_send to fall through to the public branch, fail to find
    # the guild, and mark the send as failed.
    asyncio.run(service._post_send(_send(guild_id=guild_id)))

    assert dm_called == []
    assert service.sends.mark_failed_calls and service.sends.mark_failed_calls[0][0] == 42
