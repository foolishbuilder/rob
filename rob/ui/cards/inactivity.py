from __future__ import annotations

from rob.ui.components import make_card, render
from rob.ui.render import RenderedMessage
from rob.ui.theme import COLOR_PRIMARY


def _remove_time_text(remove_at_unix: int) -> str:
    return f"<t:{remove_at_unix}:R> / <t:{remove_at_unix}:f>"


def first_inactivity_warning_card(*, display_name: str, server_name: str, remove_at_unix: int, main_chat_channel: str) -> RenderedMessage:
    return render(
        make_card(
            title="Inactivity Warning",
            body=(
                f"Hey **{display_name}**,\n\n"
                f"You are receiving this notice because you have been inactive in **{server_name}** for over a week.\n\n"
                "To help keep the server active, members may be automatically removed after **3 weeks of inactivity**.\n\n"
                "At the current schedule, if you do not become active again, "
                f"you will be removed {_remove_time_text(remove_at_unix)}."
            ),
            color=COLOR_PRIMARY,
            callout=f"If you do not wish to be removed, please become active again in {main_chat_channel}.",
            variant="warning",
        )
    )


def final_inactivity_warning_card(*, display_name: str, server_name: str, remove_at_unix: int, main_chat_channel: str) -> RenderedMessage:
    return render(
        make_card(
            title="Final Inactivity Notice",
            body=(
                f"Hey **{display_name}**,\n\n"
                f"This is your final inactivity notice before removal from **{server_name}**.\n\n"
                "At the current schedule, if you do not become active again, "
                f"you will be removed {_remove_time_text(remove_at_unix)}."
            ),
            color=COLOR_PRIMARY,
            callout=(
                f"If you wish to remain in the server, please become active again in {main_chat_channel}.\n\n"
                "-# This is a server removal only. It is not a ban."
            ),
            variant="warning",
        )
    )
