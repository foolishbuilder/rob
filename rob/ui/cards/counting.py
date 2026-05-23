from __future__ import annotations

import discord

from rob.ui.components import make_card, render
from rob.ui.render import CardSection, RenderedMessage, require_components_v2
from rob.ui.theme import COLOR_INFO, COLOR_SUCCESS


def counting_status_card(*, current_number: int, enabled: bool) -> RenderedMessage:
    return render(
        make_card(
            title="Rob | Counting",
            body="Current counting channel state.",
            color=COLOR_INFO,
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
            variant="counting",
        )
    )


def counting_same_user_reminder_card() -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=30)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("## Hold up there, speedy."),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "One number per person at a time.\n"
                "Let someone else have a go before you count again."
            ),
            accent_color=COLOR_INFO,
        )
    )
    return RenderedMessage(view=view)


def count_rescue_needed_card(*, remaining_seconds: int, deadline_unix: int) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=1800)
    remaining_seconds = max(0, remaining_seconds)
    minutes, seconds = divmod(remaining_seconds, 60)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("## Count Rescue Needed"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "The count is wobbling.\n"
                "A Sub entered the wrong number. To keep the count alive, a qualifying send to a Dom/me needs to happen before time runs out.\n\n"
                "-# Time remaining:\n"
                f"**{minutes}m {seconds:02d}s**\n\n"
                "-# Deadline:\n"
                f"<t:{deadline_unix}:R> / <t:{deadline_unix}:f>"
            ),
            accent_color=COLOR_INFO,
        )
    )
    return RenderedMessage(view=view)


def count_saved_card(*, next_number: int) -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=600)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("## Count Saved"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "Rob saw the send and duct-taped the count back together.\n"
                f"Continue from **{next_number}**."
            ),
            accent_color=COLOR_SUCCESS,
        )
    )
    return RenderedMessage(view=view)


def count_failed_card() -> RenderedMessage:
    require_components_v2()
    view = discord.ui.LayoutView(timeout=600)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay("## Count Failed"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "No qualifying send arrived in time.\n"
                "Rob has reset the count."
            ),
            accent_color=COLOR_INFO,
        )
    )
    return RenderedMessage(view=view)
