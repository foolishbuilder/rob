from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from rob.services.tldr_service import (
    ChatMessage,
    TldrService,
    extract_urls,
    filter_by_topic,
)


def _msg(author: str, content: str) -> ChatMessage:
    return ChatMessage(author=author, content=content, created_at=datetime.now(timezone.utc))


SAMPLE = [
    _msg("Alice", "Did anyone see the new leaderboard update?"),
    _msg("Bob", "Yeah the leaderboard looks great, https://robthebot.com is live"),
    _msg("Cara", "lol nice"),
    _msg("Bob", "We should schedule the event for Friday evening I think."),
]


def _run(coro):
    return asyncio.run(coro)


def test_extract_urls():
    assert extract_urls("see https://a.test/x and http://b.test") == [
        "https://a.test/x",
        "http://b.test",
    ]
    assert extract_urls("no links here") == []


def test_filter_by_topic_matches_tokens():
    matched = filter_by_topic(SAMPLE, "leaderboard")
    assert len(matched) == 2
    assert all("leaderboard" in m.content.lower() for m in matched)


def test_digest_summary_without_ollama():
    svc = TldrService(enabled=True, ollama_url=None)
    result = _run(
        svc.summarize(SAMPLE, topic=None, timeframe_label="the last 24 hours", channel_name="general")
    )
    assert result.method == "digest"
    assert result.message_count == 4
    assert result.participant_count == 3
    assert "https://robthebot.com" in result.links
    assert "Most active" in result.summary
    assert "Bob (2)" in result.summary


def test_digest_topic_summary_reports_matches():
    svc = TldrService(enabled=True, ollama_url=None)
    result = _run(
        svc.summarize(
            SAMPLE, topic="leaderboard", timeframe_label="the last 24 hours", channel_name="general"
        )
    )
    assert result.topic == "leaderboard"
    assert result.matched_count == 2
    assert result.message_count == 2
    assert "leaderboard" in result.summary.lower()


def test_empty_scope_returns_no_messages_note():
    svc = TldrService(enabled=True, ollama_url=None)
    result = _run(
        svc.summarize([], topic=None, timeframe_label="the last hour", channel_name="general")
    )
    assert result.method == "digest"
    assert "No messages" in result.summary


def test_empty_topic_scope_mentions_topic():
    svc = TldrService(enabled=True, ollama_url=None)
    result = _run(
        svc.summarize(
            SAMPLE, topic="zzzznotfound", timeframe_label="the last hour", channel_name="general"
        )
    )
    assert result.matched_count == 0
    assert "zzzznotfound" in result.summary


class _FakeOllamaResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, json=None):
        self.calls.append((url, json))
        if self._error is not None:
            raise self._error
        return self._response


def test_ollama_success_returns_ai_summary():
    session = _FakeSession(
        response=_FakeOllamaResponse(200, {"response": "- Talked about the leaderboard\n- Planned Friday event"})
    )
    svc = TldrService(
        enabled=True,
        ollama_url="http://127.0.0.1:11434",
        model="llama3.2:1b",
        session_factory=lambda: session,
    )
    result = _run(
        svc.summarize(SAMPLE, topic=None, timeframe_label="the last 24 hours", channel_name="general")
    )
    assert result.method == "ai"
    assert result.model == "llama3.2:1b"
    assert "Friday event" in result.summary
    # message/participant counts still populated from the real messages
    assert result.message_count == 4
    assert session.calls and session.calls[0][0].endswith("/api/generate")


def test_ollama_connection_error_falls_back_to_digest_and_trips_breaker():
    import aiohttp

    session = _FakeSession(error=aiohttp.ClientError("boom"))
    svc = TldrService(
        enabled=True,
        ollama_url="http://127.0.0.1:11434",
        session_factory=lambda: session,
    )
    result = _run(
        svc.summarize(SAMPLE, topic=None, timeframe_label="the last 24 hours", channel_name="general")
    )
    assert result.method == "digest"
    # Breaker tripped: the next call should skip Ollama entirely.
    assert not svc._ollama_ready()


def test_ollama_non_200_falls_back():
    session = _FakeSession(response=_FakeOllamaResponse(500, {}))
    svc = TldrService(
        enabled=True,
        ollama_url="http://127.0.0.1:11434",
        session_factory=lambda: session,
    )
    result = _run(
        svc.summarize(SAMPLE, topic=None, timeframe_label="the last 24 hours", channel_name="general")
    )
    assert result.method == "digest"


def test_ollama_null_response_falls_back_to_digest():
    # A 200 with {"response": null} must not surface the literal "None" — it
    # should fall back to the digest.
    session = _FakeSession(response=_FakeOllamaResponse(200, {"response": None}))
    svc = TldrService(
        enabled=True,
        ollama_url="http://127.0.0.1:11434",
        session_factory=lambda: session,
    )
    result = _run(
        svc.summarize(SAMPLE, topic=None, timeframe_label="today", channel_name="general")
    )
    assert result.method == "digest"
    assert "None" not in result.summary.splitlines()[0]


def test_ollama_non_dict_body_falls_back_to_digest():
    # A 200 whose JSON body is a list/string must not raise out of summarize().
    session = _FakeSession(response=_FakeOllamaResponse(200, ["unexpected"]))
    svc = TldrService(
        enabled=True,
        ollama_url="http://127.0.0.1:11434",
        session_factory=lambda: session,
    )
    result = _run(
        svc.summarize(SAMPLE, topic=None, timeframe_label="today", channel_name="general")
    )
    assert result.method == "digest"


def test_ai_summary_neutralises_mentions():
    session = _FakeSession(
        response=_FakeOllamaResponse(200, {"response": "- <@123> pinged @everyone about the event"})
    )
    svc = TldrService(
        enabled=True,
        ollama_url="http://127.0.0.1:11434",
        session_factory=lambda: session,
    )
    result = _run(
        svc.summarize(SAMPLE, topic=None, timeframe_label="today", channel_name="general")
    )
    assert "<@123>" not in result.summary
    assert "@everyone" not in result.summary
