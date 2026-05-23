from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from rob.database.repositories.models import LatestTrackedSend, LeaderboardEntry, PersonalStatsSummary
from rob.discord.cogs.leaderboards import LeaderboardsCog


class _FakeResponse:
    def __init__(self):
        self.messages: list[dict] = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


class _FakeInteraction:
    def __init__(self, *, user_id: int = 10):
        self.guild = SimpleNamespace(id=1, get_member=self._get_member)
        self.user = SimpleNamespace(id=user_id, display_name="Pat", mention=f"<@{user_id}>")
        self.response = _FakeResponse()
        self._members = {
            10: SimpleNamespace(display_name="Pat"),
            20: SimpleNamespace(display_name="Alex"),
            30: SimpleNamespace(display_name="Sam"),
        }

    def _get_member(self, user_id: int):
        return self._members.get(user_id)


class _FakeDommesRepo:
    def __init__(self, present: bool):
        self.present = present

    async def get_by_user_id(self, _guild_id: int, _user_id: int):
        return SimpleNamespace(id=1) if self.present else None


class _FakeSubsRepo:
    def __init__(self, present: bool):
        self.present = present

    async def get_by_user_id(self, _guild_id: int, _user_id: int):
        return SimpleNamespace(id=2) if self.present else None


class _FakeLeaderboardsRepo:
    async def get_domme_stats(self, *_args, **_kwargs):
        return PersonalStatsSummary(total_cents=12345, send_count=7)

    async def get_domme_rank(self, *_args, **_kwargs):
        return 1

    async def get_domme_latest_send(self, *_args, **_kwargs):
        now = datetime.now(timezone.utc)
        return LatestTrackedSend(
            id=1,
            domme_user_id=10,
            sub_user_id=20,
            sub_name="gifter",
            amount_cents=1099,
            currency="USD",
            method="paypal",
            source="manual:paypal",
            item_name="Flowers",
            item_image_url="https://example.com/item.png",
            sent_at=now,
        )

    async def get_domme_top_sending_sub(self, *_args, **_kwargs):
        return LeaderboardEntry(label="<@20>", user_id=20, total_cents=5000, send_count=2)

    async def get_sub_stats(self, *_args, **_kwargs):
        return PersonalStatsSummary(total_cents=54321, send_count=4)

    async def get_sub_latest_send(self, *_args, **_kwargs):
        now = datetime.now(timezone.utc)
        return LatestTrackedSend(
            id=2,
            domme_user_id=30,
            sub_user_id=10,
            sub_name="Pat",
            amount_cents=2099,
            currency="USD",
            method="paypal",
            source="manual:paypal",
            item_name="AirPods",
            item_image_url="https://example.com/item2.png",
            sent_at=now,
        )

    async def get_sub_top_domme(self, *_args, **_kwargs):
        return LeaderboardEntry(label="<@30>", user_id=30, total_cents=3000, send_count=2)


class _FakeBot:
    def __init__(self, *, domme_present: bool, sub_present: bool):
        self.settings = SimpleNamespace(
            throne_parse_test_sends_as_real_sends=False,
            throne_test_gifter_usernames=("marie_123",),
            throne_test_send_leaderboard_owner_user_id=None,
        )
        self.dommes_repo = _FakeDommesRepo(domme_present)
        self.subs_repo = _FakeSubsRepo(sub_present)
        self.leaderboards_repo = _FakeLeaderboardsRepo()


def test_leaderboard_is_ephemeral_stats_only_for_registered_domme_and_sub():
    interaction = _FakeInteraction(user_id=10)
    cog = LeaderboardsCog(_FakeBot(domme_present=True, sub_present=True))

    asyncio.run(LeaderboardsCog.leaderboard.callback(cog, interaction))

    assert len(interaction.response.messages) == 1
    payload = interaction.response.messages[0]
    assert payload["ephemeral"] is True
    view = payload["view"]
    text = "\n".join(
        str(getattr(item, "content", ""))
        for container in view.children
        for item in getattr(container, "children", [])
    )
    assert "Send Stats | Dom/me" in text
    assert "Send Stats | Sub" in text
    assert "👑 #1" in text


def test_leaderboard_unregistered_user_gets_registration_help():
    interaction = _FakeInteraction(user_id=999)
    cog = LeaderboardsCog(_FakeBot(domme_present=False, sub_present=False))

    asyncio.run(LeaderboardsCog.leaderboard.callback(cog, interaction))

    payload = interaction.response.messages[0]
    assert payload["ephemeral"] is True
    text = "\n".join(
        str(getattr(item, "content", ""))
        for item in payload["view"].children[0].children
    )
    assert "/register domme" in text
    assert "/register sub" in text
