from __future__ import annotations

from rob.ui.components import make_card, render
from rob.ui.copy import COUNTING_FOOTER, SUCCESS_FOOTER
from rob.ui.render import CardSection, RenderedMessage
from rob.ui.theme import COLOR_INFO, COLOR_SUCCESS


def counting_status_card(*, current_number: int, enabled: bool) -> RenderedMessage:
    return render(
        make_card(
            title="Rob | Counting",
            body="Current counting channel state.",
            color=COLOR_INFO,
            footer=COUNTING_FOOTER,
            variant="counting",
            sections=[
                CardSection(title="Enabled", text="Yes" if enabled else "No", inline=True),
                CardSection(title="Current Number", text=str(current_number), inline=True),
            ],
        )
    )


def counting_updated_card(number: int) -> RenderedMessage:
    return render(
        make_card(
            title="Rob | Count Updated",
            body=f"Counting has been set to **{number}**.",
            color=COLOR_SUCCESS,
            footer=SUCCESS_FOOTER,
            variant="counting",
        )
    )
