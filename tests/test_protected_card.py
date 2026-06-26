from __future__ import annotations

import asyncio
from types import SimpleNamespace

import discord

from rob.discord.cogs.protected import _GOFUNDME_URL, _MEMORIAL_USER_ID, ProtectedCog
from rob.ui.cards.protected import protected_member_card
from rob.ui.render import add_card_actions
from rob.ui.theme import COLOR_WHITE


def _card_text(rendered) -> str:
    return "\n".join(
        str(getattr(child, "content", ""))
        for child in rendered.view.children[0].children
    )


def test_protected_card_is_white_and_mentions_the_account():
    rendered = protected_member_card(user_id=_MEMORIAL_USER_ID, display_name="Alyssa")
    assert rendered.view.children[0].accent_color == COLOR_WHITE
    contents = _card_text(rendered)
    assert "## 🪽 Protected Member 🪽" in contents
    assert f"<@{_MEMORIAL_USER_ID}>" in contents
    assert "In loving memory" in contents


def test_protected_card_footer_uses_display_name_in_both_subtext_lines():
    rendered = protected_member_card(user_id=_MEMORIAL_USER_ID, display_name="Alyssa")
    contents = _card_text(rendered)
    # The footer renders as `-#` subtext and names the member in both lines.
    assert "-# Alyssa is shielded from the inactivity system" in contents
    assert "-# In every server backup, Alyssa's account is preserved" in contents


def test_protected_card_falls_back_when_display_name_missing():
    rendered = protected_member_card(user_id=_MEMORIAL_USER_ID, display_name=None)
    contents = _card_text(rendered)
    assert "This member is shielded" in contents


def test_protected_card_renders_into_supplied_view_with_gofundme_button():
    view = discord.ui.LayoutView(timeout=None)
    rendered = protected_member_card(
        user_id=_MEMORIAL_USER_ID,
        display_name="Alyssa",
        view=view,
    )
    add_card_actions(
        view,
        discord.ui.Button(
            label="Help Lay Alyssa Rae to Rest",
            url=_GOFUNDME_URL,
            style=discord.ButtonStyle.link,
        ),
    )
    assert rendered.view is view
    assert type(view.children[0]).__name__ == "Container"
    action_row = view.children[1]
    assert type(action_row).__name__ == "ActionRow"
    button = action_row.children[0]
    assert button.url == _GOFUNDME_URL
    assert button.style == discord.ButtonStyle.link


def test_protected_command_replies_without_pinging_the_account():
    sent: dict[str, object] = {}

    async def _reply(**kwargs):
        sent.update(kwargs)

    member = SimpleNamespace(display_name="Alyssa")
    guild = SimpleNamespace(get_member=lambda uid: member if uid == _MEMORIAL_USER_ID else None)
    ctx = SimpleNamespace(guild=guild, reply=_reply)
    bot = SimpleNamespace()
    cog = ProtectedCog(bot)

    asyncio.run(cog.protected.callback(cog, ctx))

    # The card is delivered as a Components V2 view, with mentions suppressed so
    # the memorial account is never pinged.
    assert sent["view"] is not None
    assert sent["mention_author"] is False
    allowed = sent["allowed_mentions"]
    assert allowed.users is False
    assert allowed.roles is False
    assert allowed.everyone is False
