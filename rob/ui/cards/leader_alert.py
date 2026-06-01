from __future__ import annotations

from rob.ui.components import make_card, render
from rob.ui.render import RenderedMessage
from rob.ui.theme import COLOR_LEADER_ALERT


def leader_alert_card(user_mention: str) -> RenderedMessage:
    return render(
        make_card(
            title="👑 NEW LEADER ALERT!",
            body=f"Watch out every one! {user_mention} is now #1 on the send leaderboard!",
            color=COLOR_LEADER_ALERT,
            variant="default",
            footer="To view your rank on the leaderboard, run /leaderboard",
        )
    )
