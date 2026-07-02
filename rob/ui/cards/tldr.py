from __future__ import annotations

from rob.ui.components import make_card, render
from rob.ui.render import RenderedMessage
from rob.ui.theme import COLOR_INFO

# Components V2 text blocks cap at 4000 chars; leave headroom for the truncation
# note and card chrome.
_BODY_BUDGET = 3800


def _fit(text: str, budget: int = _BODY_BUDGET) -> str:
    text = text.strip()
    if len(text) <= budget:
        return text
    note = "\n\n… summary trimmed to fit."
    return text[: budget - len(note)].rstrip() + note


def tldr_card(
    *,
    channel_name: str,
    timeframe_label: str,
    summary: str,
    method: str,
    message_count: int,
    participant_count: int,
    topic: str | None = None,
    matched_count: int | None = None,
    model: str | None = None,
    ai_message_count: int | None = None,
) -> RenderedMessage:
    if method == "ai" and model:
        engine = f"summarised by {model} (on-server)"
    else:
        engine = "quick digest"

    people = "person" if participant_count == 1 else "people"
    msgs = "message" if message_count == 1 else "messages"
    # Be honest when a busy window didn't fully fit the model's budget: the
    # summary then covers the most recent slice, not the whole timeframe.
    if (
        method == "ai"
        and ai_message_count is not None
        and 0 < ai_message_count < message_count
    ):
        count_bit = f"latest {ai_message_count} of {message_count} {msgs}"
    else:
        count_bit = f"{message_count} {msgs}"
    footer_bits = [count_bit, f"{participant_count} {people}", engine]
    footer = " · ".join(footer_bits)

    eyebrow = "🧾 TL;DR"
    if topic:
        eyebrow = f"🧾 TL;DR · {topic}"
        if matched_count is not None:
            match_word = "match" if matched_count == 1 else "matches"
            footer = f"{matched_count} {match_word} · {footer}"

    return render(
        make_card(
            title=f"#{channel_name} · {timeframe_label}",
            body=_fit(summary) or "Nothing to summarise.",
            color=COLOR_INFO,
            variant="status",
            eyebrow=eyebrow,
            footer=footer,
        )
    )
