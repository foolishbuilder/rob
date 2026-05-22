from __future__ import annotations

import time
from rob.database.repositories.models import LeaderboardEntry, LeaderboardSummary
from rob.ui.components import make_card, render
from rob.ui.copy import LEADERBOARD_FOOTER
from rob.ui.theme import COLOR_PRIMARY
from rob.utils.money import format_money_from_cents


def _line(i: int, label: str) -> str:
    return ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"#{i}"

def leaderboard_card(*, title: str, entries: list[LeaderboardEntry], summary: LeaderboardSummary, footer: str = LEADERBOARD_FOOTER):
    if not entries:
        body = "-# 🟢 Live\n\nNo sends have made it onto the board yet.\n\nRob is standing here with a clipboard and absolutely nothing to write down."
    else:
        lines=[]
        for i,e in enumerate(entries[:10],1):
            lines.append(f"{_line(i, e.label)} **{e.label}**\nAmount: {format_money_from_cents(e.total_cents)} | Total Sends: {e.send_count}")
        body = "-# 🟢 Live\n\n" + "\n\n".join(lines)
    return render(make_card(title="🏆 Thy Send Leaderboard", body=body, color=COLOR_PRIMARY, footer=footer, variant="leaderboard"))

def leaderboard_stats_card(summary: LeaderboardSummary, entries: list[LeaderboardEntry]):
    now = int(time.time())
    body = (
        f"-# Leaderboard last updated: <t:{now}:R> / <t:{now}:f>\n\n"
        f"-# Leaderboard Leader:\n**👑 {entries[0].label if entries else 'Nobody yet'} - {format_money_from_cents(entries[0].total_cents if entries else 0)}**\n\n"
        f"-# Total Dommes on Leaderboard:\n**🦹‍♀️ {summary.domme_count}**\n\n"
        f"-# Total Sends Tracked:\n**💸 {summary.send_count}**\n\n"
        f"-# Total Amount Tracked:\n**{format_money_from_cents(summary.total_cents)}**"
    )
    return render(make_card(title="🏆 Thy Send Leaderboard | Stats", body=body, color=COLOR_PRIMARY, footer=LEADERBOARD_FOOTER, variant="leaderboard"))
