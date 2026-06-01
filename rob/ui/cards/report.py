from __future__ import annotations

from rob.ui.components import make_card, render
from rob.ui.render import CardSection, RenderedMessage
from rob.ui.theme import COLOR_PRIMARY, COLOR_SUCCESS


def report_submitted_card() -> RenderedMessage:
    return render(
        make_card(
            title="Report Sent",
            body=(
                "Thanks — I've sent that through.\n"
                "If this is urgent, please also let a moderator know."
            ),
            color=COLOR_SUCCESS,
            variant="success",
        )
    )


def report_staff_card(
    *,
    reporter_mention: str,
    issue_text: str,
    server_label: str,
    submitted_unix: int,
) -> RenderedMessage:
    return render(
        make_card(
            title="Rob Issue Report",
            body=issue_text,
            color=COLOR_PRIMARY,
            variant="workflow",
            sections=[
                CardSection(title="Reporter", text=reporter_mention),
                CardSection(title="Server", text=server_label),
                CardSection(title="Submitted", text=f"<t:{submitted_unix}:R> · <t:{submitted_unix}:f>"),
            ],
        )
    )
