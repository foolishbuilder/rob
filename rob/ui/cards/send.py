from __future__ import annotations

from rob.database.repositories.models import SendRecord
from rob.ui.components import make_card, render
from rob.ui.render import CardSection
from rob.ui.theme import COLOR_INFO
from rob.utils.money import format_money_from_cents
from rob.utils.time import format_timestamp


def send_card(*, send: SendRecord, domme_label: str, sub_label: str | None):
    amount_text = "Private / hidden" if send.is_private and send.amount_cents == 0 else format_money_from_cents(send.amount_cents, send.currency)
    return render(make_card(title="Rob | New Send", body=send.item_name or "A new send was logged.", color=COLOR_INFO, footer="Posted from the shared send queue.", variant="send", sections=[CardSection(title="Domme", text=domme_label, inline=True), CardSection(title="Sender", text=sub_label or "Unclaimed", inline=True), CardSection(title="Amount", text=amount_text, inline=True), CardSection(title="Method", text=send.method or send.source, inline=True), CardSection(title="Sent At", text=format_timestamp(send.sent_at), inline=False)], image_url=send.item_image_url))
