from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import discord
import pytest

from rob.database.repositories.models import SendRecord, SendRequestRecord
from rob.discord.cogs.sends import SendsCog
from rob.services.send_request_service import SendRequestDecision


class _FakeResponse:
    def __init__(self):
        self.messages: list[dict] = []
        self.deferred = False
        self.edits: list[dict] = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)

    async def defer(self, *, ephemeral: bool = False):
        self.deferred = ephemeral

    async def edit_message(self, **kwargs):
        self.edits.append(kwargs)

    async def send_modal(self, modal):
        self.modal = modal


class _FakeFollowup:
    def __init__(self):
        self.messages: list[dict] = []

    async def send(self, **kwargs):
        self.messages.append(kwargs)


class _FakeMember:
    def __init__(self, user_id: int, display_name: str):
        self.id = user_id
        self.display_name = display_name
        self.mention = f"<@{user_id}>"
        self.sent_messages: list[dict] = []

    async def send(self, **kwargs):
        self.sent_messages.append(kwargs)


class _FakeInteraction:
    def __init__(self, *, user_id: int = 10):
        self.guild = SimpleNamespace(id=1)
        self.user = _FakeMember(user_id, "SubUser")
        self.response = _FakeResponse()
        self.followup = _FakeFollowup()
        self.message = None


def _request_record() -> SendRequestRecord:
    now = datetime.now(timezone.utc)
    return SendRequestRecord(
        id=11,
        guild_id=1,
        sub_user_id=10,
        domme_user_id=20,
        amount_cents=1099,
        currency="USD",
        method="paypal",
        note="proof",
        status="pending",
        created_at=now,
        resolved_at=None,
    )


class _FakeSendRequestsRepo:
    def __init__(self):
        self.record = _request_record()
        self.deleted: list[int] = []

    async def create(self, **_kwargs):
        return self.record

    async def delete(self, request_id: int):
        self.deleted.append(request_id)

    async def get(self, request_id: int):
        if request_id != self.record.id:
            return None
        return self.record


class _FakeSendRequestService:
    async def is_rate_limited(self, **_kwargs):
        return False

    async def approve(self, **_kwargs):
        now = datetime.now(timezone.utc)
        send = SendRecord(
            1,
            1,
            None,
            20,
            None,
            10,
            "SubUser",
            1099,
            "USD",
            "paypal",
            "send_request",
            "proof",
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
        return SendRequestDecision(
            ok=True,
            status="approved",
            send=send,
            request_sub_user_id=10,
            request_domme_user_id=20,
            amount_cents=1099,
            method="paypal",
            note="proof",
        )

    async def deny(self, **_kwargs):
        return SendRequestDecision(
            ok=True,
            status="denied",
            request_sub_user_id=10,
            request_domme_user_id=20,
            amount_cents=1099,
            method="paypal",
            note="proof",
            denial_reason="No proof",
        )


class _FakeBot:
    def __init__(self):
        self.guild_settings_repo = SimpleNamespace(get=self._get_settings)
        self.dommes_repo = SimpleNamespace(get_by_user_id=self._get_domme)
        self.send_requests_repo = _FakeSendRequestsRepo()
        self.send_request_service = _FakeSendRequestService()
        self._sub_user = _FakeMember(10, "SubUser")

    async def _get_settings(self, _guild_id: int):
        return SimpleNamespace(sub_role_id=222)

    async def _get_domme(self, _guild_id: int, user_id: int):
        if user_id == 20:
            return SimpleNamespace(id=5)
        return None

    def get_user(self, user_id: int):
        if user_id == 10:
            return self._sub_user
        return None

    async def fetch_user(self, user_id: int):
        if user_id == 10:
            return self._sub_user
        raise discord.NotFound(response=None, message="not found")  # pragma: no cover


def test_sendrequest_requires_sub_role_config(monkeypatch: pytest.MonkeyPatch):
    bot = _FakeBot()
    async def _get_settings(_guild_id: int):
        return SimpleNamespace(sub_role_id=None)

    bot.guild_settings_repo = SimpleNamespace(get=_get_settings)
    interaction = _FakeInteraction(user_id=10)
    cog = SendsCog(bot)
    domme = _FakeMember(20, "DommeUser")
    monkeypatch.setattr("rob.discord.cogs.sends.member_has_role", lambda *_args, **_kwargs: True)

    asyncio.run(
        SendsCog.send_request.callback(
            cog,
            interaction,
            domme=domme,
            amount=10.0,
            service=SimpleNamespace(value="paypal"),
            note=None,
        )
    )

    assert interaction.response.messages[0]["ephemeral"] is True


def test_sendrequest_sends_ephemeral_confirmation_and_domme_dm(monkeypatch: pytest.MonkeyPatch):
    bot = _FakeBot()
    interaction = _FakeInteraction(user_id=10)
    cog = SendsCog(bot)
    domme = _FakeMember(20, "DommeUser")
    monkeypatch.setattr("rob.discord.cogs.sends.member_has_role", lambda *_args, **_kwargs: True)

    asyncio.run(
        SendsCog.send_request.callback(
            cog,
            interaction,
            domme=domme,
            amount=10.0,
            service=SimpleNamespace(value="paypal"),
            note="proof",
        )
    )

    assert interaction.response.deferred is True
    assert interaction.followup.messages[0]["ephemeral"] is True
    assert domme.sent_messages
    dm_view = domme.sent_messages[0]["view"]
    assert type(dm_view.children[0]).__name__ == "Container"
    section_accessories = [
        getattr(child, "accessory", None)
        for child in dm_view.children[0].children
        if type(child).__name__ == "Section"
    ]
    assert any(isinstance(accessory, discord.ui.Button) for accessory in section_accessories)
    dm_text = "\n".join(
        str(getattr(child, "content", ""))
        for child in dm_view.children[0].children
    )
    assert "Hello **DommeUser**" in dm_text
    assert "Hello **SubUser**" not in dm_text


def test_sendrequest_buttons_only_target_domme_can_act(monkeypatch: pytest.MonkeyPatch):
    bot = _FakeBot()
    interaction = _FakeInteraction(user_id=10)
    cog = SendsCog(bot)
    domme = _FakeMember(20, "DommeUser")
    monkeypatch.setattr("rob.discord.cogs.sends.member_has_role", lambda *_args, **_kwargs: True)

    asyncio.run(
        SendsCog.send_request.callback(
            cog,
            interaction,
            domme=domme,
            amount=10.0,
            service=SimpleNamespace(value="paypal"),
            note="proof",
        )
    )

    dm_view = domme.sent_messages[0]["view"]
    container = dm_view.children[0]
    buttons = [
        child.accessory
        for child in container.children
        if type(child).__name__ == "Section" and isinstance(getattr(child, "accessory", None), discord.ui.Button)
    ]
    outsider_interaction = _FakeInteraction(user_id=999)
    outsider_interaction.message = SimpleNamespace()
    asyncio.run(buttons[0].callback(outsider_interaction))
    assert outsider_interaction.response.messages[0]["ephemeral"] is True
