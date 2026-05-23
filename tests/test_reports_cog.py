from __future__ import annotations

import asyncio
from types import SimpleNamespace

from rob.discord.cogs.reports import ReportsCog


class _FakeDestination:
    def __init__(self):
        self.messages: list[dict] = []

    async def send(self, **kwargs):
        self.messages.append(kwargs)


class _FakeResponse:
    def __init__(self):
        self.messages: list[dict] = []
        self.modal = None

    async def send_modal(self, modal):
        self.modal = modal

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


class _FakeInteraction:
    def __init__(self):
        self.guild = SimpleNamespace(id=1, name="GuildName")
        self.user = SimpleNamespace(id=10, mention="<@10>")
        self.response = _FakeResponse()


class _FakeBot:
    def __init__(self):
        self.guild_settings_repo = SimpleNamespace(get=self._get_settings)
        self.destination = _FakeDestination()

    async def _get_settings(self, _guild_id: int):
        return SimpleNamespace(report_channel_id=123)

    async def application_info(self):
        return SimpleNamespace(owner=self.destination)


def test_report_command_opens_modal():
    bot = _FakeBot()
    cog = ReportsCog(bot)
    interaction = _FakeInteraction()

    asyncio.run(ReportsCog.report.callback(cog, interaction, screenshot=None))

    assert interaction.response.modal is not None


def test_report_requires_yes_acknowledgement():
    bot = _FakeBot()
    cog = ReportsCog(bot)
    interaction = _FakeInteraction()

    async def _no_destination(_interaction):
        return bot.destination

    cog._resolve_destination = _no_destination  # type: ignore[method-assign]
    asyncio.run(
        cog.submit_report(
            interaction,
            issue_text="something broke",
            acknowledgement="NO",
            attachment=None,
        )
    )

    assert interaction.response.messages[0]["ephemeral"] is True


def test_report_posts_to_configured_destination_and_confirms_user():
    bot = _FakeBot()
    cog = ReportsCog(bot)
    interaction = _FakeInteraction()

    async def _destination(_interaction):
        return bot.destination

    cog._resolve_destination = _destination  # type: ignore[method-assign]
    asyncio.run(
        cog.submit_report(
            interaction,
            issue_text="send queue stalled",
            acknowledgement="YES",
            attachment=None,
        )
    )

    assert bot.destination.messages
    assert interaction.response.messages[0]["ephemeral"] is True
