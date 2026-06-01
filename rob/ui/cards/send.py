from __future__ import annotations

from rob.database.repositories.models import SendRecord
from rob.ui.components import make_card, render
from rob.ui.theme import COLOR_SEND
from rob.utils.money import format_money_from_cents, format_money_with_currency_name


def _amount_text(send: SendRecord) -> str:
    currency = (send.currency or "USD").upper()
    if currency == "USD":
        usd = format_money_from_cents(send.amount_cents, "USD")
        original_currency = (send.original_currency or "").upper()
        if send.original_amount_cents is not None and original_currency and original_currency != "USD":
            original = format_money_with_currency_name(send.original_amount_cents, original_currency)
            return f"{usd} (converted from {original})"
        return usd
    return format_money_with_currency_name(send.amount_cents, send.currency)


def send_card(
    *,
    send: SendRecord,
    domme_label: str,
    sub_display: str,
    rank: int | None = None,
    adjustment_note: str | None = None,
):
    del rank
    if send.source == "send_request":
        expected_fallback_note = f"Manual send via {send.method}" if send.method else "Manual send"
        lines = [
            f"**Sub:** {sub_display}",
            f"**Amount:** {_amount_text(send)}",
        ]
        if send.item_name and send.item_name != expected_fallback_note:
            lines.append(f"**Note:** {send.item_name}")
        lines.append(f"**Service:** {send.method or 'other'}")
        body = "\n\n".join(lines)
    else:
        body = (
            f"**Sub:** {sub_display}\n\n"
            f"**Amount:** {_amount_text(send)}\n\n"
            f"**Item:** {send.item_name or 'Mystery send'}"
        )

    if adjustment_note:
        body = f"{adjustment_note}\n\n{body}"

    return render(
        make_card(
            title=f"New Send to {domme_label}!",
            body=body,
            color=COLOR_SEND,
            variant="send",
            thumbnail_url=send.item_image_url,
            footer="Rob kept the paperwork tidy.",
        )
    )
