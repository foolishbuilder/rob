from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from rob.services.bot_ops_server import BotOpsServer


class _FakeRequest:
    def __init__(
        self,
        *,
        payload: dict | None = None,
        form_payload: dict | None = None,
        headers: dict[str, str] | None = None,
    ):
        self._payload = payload or {}
        self._form_payload = form_payload or {}
        self.headers = headers or {}
        self.match_info: dict[str, str] = {}

    async def json(self):
        if self._payload == "__error__":
            raise ValueError("json parse failed")
        return self._payload

    async def post(self):
        return _FakeForm(self._form_payload)


class _FakeForm(dict):
    def getall(self, key):
        value = self[key]
        if isinstance(value, list):
            return value
        return [value]


class _FakeSendQueue:
    def __init__(self):
        self.notified: list[int] = []

    async def notify_send(self, send_id: int) -> None:
        self.notified.append(send_id)


class _FakeRegistrationService:
    def __init__(self):
        self.calls: list[dict] = []

    async def register_sub(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(sub=SimpleNamespace(id=7, discord_user_id=kwargs["discord_user_id"]), send_names=tuple(kwargs["send_names"]))


class _FakeSendChangeRequestService:
    def __init__(self):
        self.calls: list[dict] = []

    async def create_send_add_request(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id=11,
            action="send_add",
            status="pending",
            domme_user_id=555,
        )


def test_bot_ops_process_send_endpoint_enqueues_specific_send():
    send_queue = _FakeSendQueue()
    bot = SimpleNamespace(send_queue_service=send_queue, user=SimpleNamespace(id=123))
    server = BotOpsServer(bot=bot, host="127.0.0.1", port=8811, secret="shared")
    request = _FakeRequest(
        payload={"send_id": 42, "guild_id": 99},
        headers={"X-Rob-Ops-Secret": "shared"},
    )

    response = asyncio.run(server._handle_process_send(request))

    assert response.status == 200
    assert send_queue.notified == [42]
    body = json.loads(response.text)
    assert body == {"ok": True, "queued": True, "send_id": 42, "guild_id": 99}


def test_bot_ops_process_send_endpoint_requires_secret():
    send_queue = _FakeSendQueue()
    bot = SimpleNamespace(send_queue_service=send_queue, user=SimpleNamespace(id=123))
    server = BotOpsServer(bot=bot, host="127.0.0.1", port=8811, secret="shared")
    request = _FakeRequest(payload={"send_id": 42}, headers={})

    response = asyncio.run(server._handle_process_send(request))

    assert response.status == 403
    assert send_queue.notified == []


def test_bot_ops_add_sub_accepts_form_payload_send_names_string():
    registration_service = _FakeRegistrationService()
    bot = SimpleNamespace(
        registration_service=registration_service,
        user=SimpleNamespace(id=123),
    )
    server = BotOpsServer(bot=bot, host="127.0.0.1", port=8811, secret="shared")
    request = _FakeRequest(
        payload="__error__",
        form_payload={
            "discord_user_id": "42",
            "send_names": "alpha, beta, gamma",
        },
        headers={"X-Rob-Ops-Secret": "shared"},
    )
    request.match_info["guild_id"] = "99"

    response = asyncio.run(server._handle_add_sub(request))

    assert response.status == 200
    assert registration_service.calls == [
        {
            "guild_id": 99,
            "discord_user_id": 42,
            "send_names": ["alpha", "beta", "gamma"],
        }
    ]


def test_bot_ops_send_add_request_endpoint_uses_approval_service():
    approval_service = _FakeSendChangeRequestService()
    bot = SimpleNamespace(
        send_change_request_service=approval_service,
        user=SimpleNamespace(id=123),
    )
    server = BotOpsServer(bot=bot, host="127.0.0.1", port=8811, secret="shared")
    request = _FakeRequest(
        payload={
            "domme_lookup": "missadore",
            "amount": "25.50",
            "sub_name": "pat",
            "requested_by": "rob@test",
        },
        headers={"X-Rob-Ops-Secret": "shared"},
    )
    request.match_info["guild_id"] = "99"

    response = asyncio.run(server._handle_request_send_add(request))

    assert response.status == 200
    assert approval_service.calls == [
        {
            "guild_id": 99,
            "domme_lookup": "missadore",
            "amount_cents": 2550,
            "sub_name": "pat",
            "requested_by": "rob@test",
            "currency": "USD",
            "method": "manual",
            "note": None,
        }
    ]
