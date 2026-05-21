from __future__ import annotations

import discord

from rob.ui.components import make_card, render
from rob.ui.copy import SUCCESS_FOOTER
from rob.ui.render import CardSection, RenderedMessage
from rob.ui.theme import COLOR_PRIMARY, COLOR_SUCCESS


def registration_card(*, title: str, summary: str, details: list[tuple[str, str]] | None = None, view: discord.ui.LayoutView | None = None) -> RenderedMessage:
    sections = [CardSection(title=name, text=value) for name, value in (details or [])]
    return render(make_card(title=title, body=summary, color=COLOR_SUCCESS, footer=SUCCESS_FOOTER, sections=sections, variant="success"), view=view)


def domme_registered_card(*, view: discord.ui.LayoutView | None = None) -> RenderedMessage:
    return render(
        make_card(
            title="You're registered!",
            body=(
                "Thanks for entrusting Rob with tracking your Throne sends!\n\n"
                "Before we can fully start, there’s just one more thing I need you to do. "
                "In order for Rob to correctly receive your Throne sends, you’ll need to pop a special URL into Throne.\n\n"
                "Because that link is secret, I’ve sent you a DM to help get it sorted."
            ),
            color=COLOR_SUCCESS,
            footer=SUCCESS_FOOTER,
            variant="success",
        ),
        view=view,
    )


def throne_setup_card(description: str, *, image_url: str | None = None, view: discord.ui.LayoutView | None = None) -> RenderedMessage:
    return render(make_card(title="Throne Tracking Setup!", body=description, color=COLOR_PRIMARY, image_url=image_url, variant="setup"), view=view)
