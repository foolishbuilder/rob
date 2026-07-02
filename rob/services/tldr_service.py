"""Chat TL;DR summariser.

Two summarisation paths, both fully in-house (no chat data ever leaves the
host):

* an **extractive digest** built with plain Python (participants, links,
  highlights, topic matches) that always works, and
* an optional **natural-language summary** produced by a small local model
  served by `Ollama <https://ollama.com>`_ over loopback. When Ollama is not
  reachable Rob silently falls back to the digest, so the feature degrades
  gracefully instead of failing.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp

log = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s<>|]+", re.IGNORECASE)
# How long to stop trying Ollama after a connection failure, so a down server
# doesn't add its connect timeout to every /tldr call.
_OLLAMA_BACKOFF_SECONDS = 120
# Upper bound on the transcript handed to the local model; small models have
# small context windows, so keep the most recent messages within this budget.
_AI_TRANSCRIPT_CHAR_BUDGET = 8000


@dataclass(frozen=True)
class ChatMessage:
    """A single human chat message, decoupled from discord.py for testability."""

    author: str
    content: str
    created_at: datetime


@dataclass(frozen=True)
class TldrResult:
    summary: str
    method: str  # "ai" | "digest"
    message_count: int
    participant_count: int
    topic: str | None = None
    model: str | None = None
    matched_count: int | None = None
    links: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    return " ".join(text.split()).strip()


def _truncate(text: str, limit: int) -> str:
    text = _clean(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def extract_urls(text: str) -> list[str]:
    return _URL_RE.findall(text or "")


def filter_by_topic(messages: list[ChatMessage], topic: str) -> list[ChatMessage]:
    """Messages whose text contains any whitespace-separated token of ``topic``
    (case-insensitive). A loose match on purpose — the AI path narrows further."""

    stripped = topic.strip()
    if not stripped:
        return list(messages)
    tokens = [t.lower() for t in re.split(r"\s+", stripped) if len(t) >= 2]
    if not tokens:
        # Very short topic (e.g. one word under 2 chars): match it literally
        # rather than falling back to "everything".
        tokens = [stripped.lower()]
    matched: list[ChatMessage] = []
    for message in messages:
        lowered = message.content.lower()
        if any(token in lowered for token in tokens):
            matched.append(message)
    return matched


class TldrService:
    def __init__(
        self,
        *,
        enabled: bool = True,
        ollama_url: str | None = None,
        model: str = "llama3.2:1b",
        request_timeout_seconds: int = 45,
        max_messages: int = 400,
        session_factory=None,
    ) -> None:
        self.enabled = enabled
        self.ollama_url = ollama_url.rstrip("/") if ollama_url else None
        self.model = model
        self.request_timeout_seconds = max(1, request_timeout_seconds)
        self.max_messages = max(1, max_messages)
        # Injectable for tests; defaults to a real aiohttp session per request.
        self._session_factory = session_factory or self._default_session
        self._ollama_disabled_until = 0.0

    def _default_session(self) -> aiohttp.ClientSession:
        timeout = aiohttp.ClientTimeout(total=self.request_timeout_seconds)
        return aiohttp.ClientSession(timeout=timeout)

    @property
    def ai_available(self) -> bool:
        return bool(self.ollama_url)

    async def summarize(
        self,
        messages: list[ChatMessage],
        *,
        topic: str | None = None,
        timeframe_label: str,
        channel_name: str,
    ) -> TldrResult:
        topic = (topic or "").strip() or None
        scope = messages if topic is None else filter_by_topic(messages, topic)
        matched_count = None if topic is None else len(scope)
        participants = sorted({m.author for m in scope})
        links: list[str] = []
        for message in scope:
            links.extend(extract_urls(message.content))

        base = TldrResult(
            summary="",
            method="digest",
            message_count=len(scope),
            participant_count=len(participants),
            topic=topic,
            matched_count=matched_count,
            links=_dedupe(links),
        )

        if not scope:
            return _replace(
                base,
                summary=self._empty_summary(topic, timeframe_label, channel_name),
            )

        if self.ai_available and self._ollama_ready():
            ai_summary = await self._summarize_with_ollama(
                scope, topic=topic, timeframe_label=timeframe_label, channel_name=channel_name
            )
            if ai_summary:
                return _replace(base, summary=ai_summary, method="ai", model=self.model)

        return _replace(base, summary=self._build_digest(scope, topic=topic))

    # -- Ollama path -------------------------------------------------------

    def _ollama_ready(self) -> bool:
        return time.monotonic() >= self._ollama_disabled_until

    def _trip_ollama_breaker(self) -> None:
        self._ollama_disabled_until = time.monotonic() + _OLLAMA_BACKOFF_SECONDS

    def _build_prompt(
        self,
        messages: list[ChatMessage],
        *,
        topic: str | None,
        timeframe_label: str,
        channel_name: str,
    ) -> str:
        lines: list[str] = []
        used = 0
        # Keep the most recent messages that fit the budget, then restore order.
        for message in reversed(messages):
            author = _clean(message.author) or "someone"
            text = _clean(message.content)
            if not text:
                continue
            line = f"{author}: {text}"
            if used + len(line) + 1 > _AI_TRANSCRIPT_CHAR_BUDGET:
                break
            lines.append(line)
            used += len(line) + 1
        lines.reverse()
        transcript = "\n".join(lines)

        focus = (
            f'Focus ONLY on anything related to the topic "{topic}". '
            "If the chat does not discuss it, say so in one sentence.\n"
            if topic
            else ""
        )
        return (
            "You are Rob, a Discord assistant. Write a short, neutral TL;DR of the "
            f"chat from #{channel_name} ({timeframe_label}).\n"
            f"{focus}"
            "Use 3-6 concise bullet points, each starting with '- '. Summarise what "
            "was discussed and any decisions or outcomes. Do not add a preamble, do "
            "not invent details, and never use @ mentions. If the chat is only "
            "small talk, say that briefly.\n\n"
            "Chat transcript:\n"
            f"{transcript}\n\n"
            "TL;DR:"
        )

    async def _summarize_with_ollama(
        self,
        messages: list[ChatMessage],
        *,
        topic: str | None,
        timeframe_label: str,
        channel_name: str,
    ) -> str | None:
        prompt = self._build_prompt(
            messages, topic=topic, timeframe_label=timeframe_label, channel_name=channel_name
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        url = f"{self.ollama_url}/api/generate"
        try:
            async with self._session_factory() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        log.warning("Ollama returned HTTP %s for /tldr.", response.status)
                        self._trip_ollama_breaker()
                        return None
                    data = await response.json()
            # Parse inside the guard so a null/non-dict body can never escape.
            raw = data.get("response") if isinstance(data, dict) else None
            text = raw if isinstance(raw, str) else ""
        except (aiohttp.ClientError, TimeoutError) as exc:
            # TimeoutError covers aiohttp's total-timeout (asyncio.TimeoutError is
            # an alias on 3.11+); both mean "server slow/unreachable", not a bug.
            log.info("Ollama unavailable for /tldr (%s); using digest fallback.", exc)
            self._trip_ollama_breaker()
            return None
        except Exception:  # pragma: no cover - defensive; never break the command
            log.exception("Unexpected error calling Ollama for /tldr.")
            self._trip_ollama_breaker()
            return None

        summary = _clean_summary(text)
        return summary or None

    # -- Extractive digest -------------------------------------------------

    def _empty_summary(self, topic: str | None, timeframe_label: str, channel_name: str) -> str:
        if topic:
            return (
                f"No messages about **{topic}** were found in #{channel_name} "
                f"for {timeframe_label}."
            )
        return f"No messages were found in #{channel_name} for {timeframe_label}."

    def _build_digest(self, messages: list[ChatMessage], *, topic: str | None) -> str:
        counts = Counter(m.author for m in messages)
        top = counts.most_common(5)
        top_line = ", ".join(f"{author} ({n})" for author, n in top)

        links = _dedupe(url for m in messages for url in extract_urls(m.content))

        highlights = _pick_highlights(messages, limit=4)

        sections: list[str] = []
        if topic:
            sections.append(f'Here\'s what came up about **{topic}**:')
        sections.append(f"**Most active:** {top_line}")
        if links:
            shown = links[:3]
            more = f" (+{len(links) - len(shown)} more)" if len(links) > len(shown) else ""
            sections.append("**Links shared:** " + ", ".join(shown) + more)
        if highlights:
            bullet_lines = "\n".join(f"- {_truncate(h, 220)}" for h in highlights)
            sections.append("**Highlights:**\n" + bullet_lines)
        return "\n\n".join(sections)


def _pick_highlights(messages: list[ChatMessage], *, limit: int) -> list[str]:
    """A few representative lines: the longest, most substantive messages,
    kept in chronological order and de-duplicated."""

    candidates = [
        (m.author, _clean(m.content))
        for m in messages
        if len(_clean(m.content)) >= 20
    ]
    # Rank by length (proxy for substance) but keep chronological presentation.
    ranked = sorted(range(len(candidates)), key=lambda i: len(candidates[i][1]), reverse=True)
    chosen = sorted(ranked[:limit])
    seen: set[str] = set()
    out: list[str] = []
    for i in chosen:
        author, text = candidates[i]
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f"{author}: {text}")
    return out


def _dedupe(items) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _clean_summary(text: str) -> str:
    text = text.strip()
    # Neutralise any stray mentions the model may have echoed from the chat.
    text = text.replace("@everyone", "everyone").replace("@here", "here")
    text = re.sub(r"<@!?(\d+)>", "someone", text)
    return text.strip()


def _replace(result: TldrResult, **changes) -> TldrResult:
    from dataclasses import replace

    return replace(result, **changes)
