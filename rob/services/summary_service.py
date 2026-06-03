from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging

import discord

from rob.database.repositories.dommes import DommesRepository
from rob.database.repositories.sends import SendsRepository
from rob.discord.guilds import TEST_GUILD_ID
from rob.ui.cards.summary import summary_card
from rob.utils.money import format_money_from_cents

log = logging.getLogger(__name__)


_CADENCE_DAYS = {"weekly": 7, "fortnightly": 14, "monthly": 30}


class SummaryService:
    def __init__(
        self,
        *,
        bot: discord.Client,
        dommes: DommesRepository,
        sends: SendsRepository,
        run_interval_seconds: int = 86_400,
    ) -> None:
        self.bot = bot
        self.dommes = dommes
        self.sends = sends
        self.run_interval_seconds = run_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="rob-summary-service")

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _run(self) -> None:
        await self.bot.wait_until_ready()
        while not self._stopping:
            try:
                await self.process_due_summaries()
            except Exception:
                log.exception("Summary service cycle failed.")
            await asyncio.sleep(self.run_interval_seconds)

    async def process_due_summaries(self) -> None:
        dommes = await self.dommes.list_for_guild(TEST_GUILD_ID)
        now = datetime.now(timezone.utc)
        for domme in dommes:
            if domme.notification_mode not in {"private", "private_leaderboard"}:
                continue
            cadence = domme.summary_cadence or "weekly"
            days = _CADENCE_DAYS.get(cadence, 7)
            if domme.last_summary_sent_at is not None and domme.last_summary_sent_at > now - timedelta(days=days):
                continue
            period_start = now - timedelta(days=days)
            sends = await self.sends.list_sends_for_domme(domme.guild_id, domme.discord_user_id, limit=500)
            sends = [send for send in sends if send.sent_at >= period_start]
            total_cents = sum(send.amount_cents for send in sends)
            sender_names = [send.sub_name or "someone" for send in sends]
            user = self.bot.get_user(domme.discord_user_id)
            if user is None:
                user = await self.bot.fetch_user(domme.discord_user_id)
            period = cadence
            next_period = "next week" if cadence == "weekly" else "next fortnight" if cadence == "fortnightly" else "next month"
            rendered = summary_card(
                display_name=getattr(user, "display_name", getattr(user, "name", str(domme.discord_user_id))),
                period=period,
                next_period=next_period,
                send_count=len(sends),
                total_amount=format_money_from_cents(total_cents),
                sender_names=sender_names,
            )
            await user.send(**rendered.send_kwargs())
            await self.dommes.set_last_summary_sent_at(domme_id=domme.id)
