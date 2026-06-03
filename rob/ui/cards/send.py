from __future__ import annotations

import hashlib

import discord

from rob.database.repositories.models import SendRecord
from rob.ui.render import RenderedMessage, require_components_v2
from rob.ui.theme import COLOR_SEND
from rob.utils.money import format_money_from_cents, format_money_with_currency_name

SEND_TITLES = [
    "✨ Something just came in for {domme}",
    "💸 {domme} just received a send",
    "🎁 A little something arrived for {domme}",
    "👀 Oh, a send just landed for {domme}",
    "💌 {domme}, you have got a send",
    "✨ The send tracker has good news for {domme}",
    "🎀 Something lovely just came through for {domme}",
    "💸 Rob is pleased to report a send for {domme}",
    "🌟 A send just found its way to {domme}",
    "💝 {domme} was just treated to something nice",
]

SEND_BODIES = [
    "Looks like {sub} was feeling generous. They picked up {item} for {domme}, {amount} well spent if you ask Rob.",
    "{sub} just sent {domme} something nice. {item}, {amount}. Rob approves.",
    "{domme} can thank {sub} for this one. {item} just came through for {amount}.",
    "Rob has got good news. {sub} just treated {domme} to {item}, {amount} worth of thoughtfulness right there.",
    "{sub} showed up for {domme} today. {item}, coming in at {amount}. A good day.",
    "A {amount} send just landed. {sub} picked out {item} for {domme} and honestly? Great taste.",
    "{sub} has been thinking of {domme}. {amount} worth of {item} to prove it.",
    "Not a bad send at all. {sub} went with {item} for {domme}, {amount} total. Rob is pleased to report it.",
    "{domme} just got a little treat from {sub}. {item}, {amount}. Rob noticed immediately. Rob always notices.",
]

SEND_BODIES_ANON = [
    "Someone is keeping things mysterious. {item} just arrived for {domme}, {amount} worth of anonymous thoughtfulness.",
    "A secret admirer came through for {domme} today. {item}, {amount}. Rob knows nothing. Rob sees everything.",
    "{domme} has a secret admirer and they have got good taste. {item} just landed for {amount}.",
    "No name, no fuss. Just {item} showing up for {domme} at {amount}. Rob respects the mystery.",
    "Whoever sent this wants to stay unknown, but Rob still logged it. {item} for {domme}, {amount}.",
]

SEND_FOOTERS = [
    "🤓 Fun Fact: Rob will tell you of a send faster than Throne.",
    "📋 Rob has logged this send and is very proud of himself.",
    "👀 Rob saw that. Rob sees everything.",
    "📬 Delivered with care. You are welcome.",
    "🗂️ Filed, logged, and accounted for. Rob does not miss.",
    "☕ Rob processed this between sips of his morning coffee.",
    "🤝 Another one for the books.",
    "📡 Throne sent the signal. Rob was already listening.",
    "🏃 Rob got here first. As always.",
    "💼 Consider this send officially on the record.",
    "🎩 Rob would tip his hat but he is very busy.",
    "🔔 You rang? Well, Throne did. Rob answered.",
    "📊 Statisticians love this one weird send tracker.",
    "😌 All in a day's work for Rob.",
    "🕵️ Rob has been watching the webhook. Patiently. Always patiently.",
    "⚡ Faster than your refresh button.",
    "🤌 Tracked. Logged. Perfection.",
]


def _seeded_pick(pool: list[str], send_id: int, salt: str) -> str:
    digest = hashlib.md5(f"{send_id}:{salt}".encode()).digest()
    return pool[int.from_bytes(digest, "big") % len(pool)]


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
    require_components_v2()
    view = discord.ui.LayoutView(timeout=1800)

    if send.source == "send_request":
        lines = [
            f"Method: {send.method or 'manual'}",
            f"Amount: {_amount_text(send)}",
            f"Sub: {sub_display}",
        ]
        if send.item_name:
            lines.append(f"Note: {send.item_name}")
        children: list[discord.ui.Item] = [
            discord.ui.TextDisplay(f"## 💸 Manual send for {domme_label}"),
        ]
        if adjustment_note:
            children.append(discord.ui.TextDisplay(adjustment_note))
        children.extend([discord.ui.Separator(), discord.ui.TextDisplay("\n".join(lines))])
        view.add_item(discord.ui.Container(*children, accent_color=COLOR_SEND))
        return RenderedMessage(view=view)

    item = send.item_name or "a mystery send"
    amount = _amount_text(send)
    title = _seeded_pick(SEND_TITLES, send.id, "title").format(domme=domme_label)
    if sub_display == "a secret admirer":
        body = _seeded_pick(SEND_BODIES_ANON, send.id, "body").format(
            domme=domme_label,
            item=item,
            amount=amount,
        )
    else:
        body = _seeded_pick(SEND_BODIES, send.id, "body").format(
            sub=sub_display,
            domme=domme_label,
            item=item,
            amount=amount,
        )
    footer = _seeded_pick(SEND_FOOTERS, send.id, "footer")
    relative_timestamp = f"<t:{int(send.sent_at.timestamp())}:R>"

    children = [discord.ui.TextDisplay(f"## {title}")]
    if adjustment_note:
        children.append(discord.ui.TextDisplay(adjustment_note))
    children.append(discord.ui.Separator())
    if send.item_image_url:
        children.append(
            discord.ui.Section(
                discord.ui.TextDisplay(body),
                accessory=discord.ui.Thumbnail(media=send.item_image_url),
            )
        )
    else:
        children.append(discord.ui.TextDisplay(body))
    children.extend(
        [
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"-# {footer} · {relative_timestamp}"),
        ]
    )
    view.add_item(discord.ui.Container(*children, accent_color=COLOR_SEND))
    return RenderedMessage(view=view)
