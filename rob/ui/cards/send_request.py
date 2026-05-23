from __future__ import annotations

import discord

from rob.database.repositories.models import SendRequestRecord
from rob.ui.render import RenderedMessage, require_components_v2
from rob.ui.theme import COLOR_SEND
from rob.utils.money import format_money_with_currency_name


def send_request_sent_card(*, domme_mention: str) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=1800)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("## Send Request Sent!"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                f"I've sent your request for a send to be tracked to {domme_mention}.\n"
                "If allowed, I'll send a follow up DM to let you know it worked."
            ),
            accent_color=COLOR_SEND,
        )
    )
    return RenderedMessage(view=view)


def send_request_domme_review_card(
    *,
    sub_mention: str,
    sub_display_name: str,
    amount_cents: int,
    currency: str,
    service: str,
    note: str | None,
    accept_button: discord.ui.Button | None = None,
    deny_button: discord.ui.Button | None = None,
) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=60 * 60 * 24)
    details = (
        "-# Amount:\n"
        f"**{format_money_with_currency_name(amount_cents, currency)}**\n\n"
        "-# Service Used:\n"
        f"**{service}**\n\n"
        "-# Note:\n"
        f"**{note or 'No note provided'}**"
    )
    children: list[discord.ui.Item] = [
        discord.ui.TextDisplay(f"## New Send Track Request from {sub_mention}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(
            f"Hello **{sub_display_name}**,\n"
            f"{sub_mention} has requested for a send made to you to be tracked by Rob. Here are the submitted details:\n"
            "-# If these are correct: please use the buttons below to accept or deny the send!"
        ),
        discord.ui.Separator(),
        discord.ui.TextDisplay(details),
    ]
    if accept_button is not None:
        children.extend(
            [
                discord.ui.Separator(),
                discord.ui.Section(
                    discord.ui.TextDisplay("Approve this request and log it to the send tracker."),
                    accessory=accept_button,
                ),
            ]
        )
    if deny_button is not None:
        children.append(
            discord.ui.Section(
                discord.ui.TextDisplay("Deny this request and provide a reason."),
                accessory=deny_button,
            )
        )
    view.add_item(discord.ui.Container(*children, accent_color=COLOR_SEND))
    return RenderedMessage(view=view)


def send_request_sub_accepted_dm_card(
    *,
    sub_display_name: str,
    domme_display_name: str,
    amount_cents: int,
    currency: str,
    service: str,
) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=1800)
    body = (
        f"Hey **{sub_display_name}**,\n"
        f"**{domme_display_name}** has accepted your send of {format_money_with_currency_name(amount_cents, currency)} via {service} "
        "and this has now been entered into the Send Tracker.\n"
        "If something doesn't look right or something went wrong, please use /report either in DMs or in the Server."
    )
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("## Send Accepted"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(body),
            accent_color=COLOR_SEND,
        )
    )
    return RenderedMessage(view=view)


def send_request_sub_denied_dm_card(
    *,
    sub_display_name: str,
    domme_display_name: str,
    amount_cents: int,
    currency: str,
    service: str,
    reason: str,
) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=1800)
    body = (
        f"Hey **{sub_display_name}**,\n"
        f"**{domme_display_name}** has not accepted your send of {format_money_with_currency_name(amount_cents, currency)} via {service} "
        "with the following reason:"
    )
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("## Send Not Accepted"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(body),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"*\"{reason}\"*"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "If you believe this is a mistake, please contact **Dom/me**.\n"
                "(NOTE: This is not a form of consent to DM this individual without request.)"
            ),
            accent_color=COLOR_SEND,
        )
    )
    return RenderedMessage(view=view)


def send_request_resolution_card(*, title: str, body: str) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=600)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(f"## {title}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(body),
            accent_color=COLOR_SEND,
        )
    )
    return RenderedMessage(view=view)


def send_request_review_card(request: SendRequestRecord, domme_display_name: str) -> RenderedMessage:
    return send_request_domme_review_card(
        sub_mention=f"<@{request.sub_user_id}>",
        sub_display_name=domme_display_name,
        amount_cents=request.amount_cents,
        currency=request.currency,
        service=request.method,
        note=request.note,
    )
