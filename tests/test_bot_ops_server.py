from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from rob.services.bot_ops_server import BotOpsServer


class _FakeRequest:
    def __init__(self, *, payload: dict | None = None, headers: dict[str, str] | None = None):
        self._payload = payload or {}
        self.headers = headers or {}
        self.match_info: dict[str, str] = {}

    async def json(self):
        return self._payload


class _FakeSendQueue:
    def __init__(self):
        self.notified: list[int] = []

    async def notify_send(self, send_id: int) -> None:
        self.notified.append(send_id)


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
