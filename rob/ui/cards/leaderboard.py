from __future__ import annotations

import time

from rob.database.repositories.models import LeaderboardEntry, LeaderboardSummary
from rob.services.leaderboard_status import LeaderboardStatus, render_leaderboard_status
from rob.ui.components import make_card, render
from rob.ui.render import CardSection, RenderedMessage
from rob.ui.theme import COLOR_LEADERBOARD
from rob.utils.money import format_money_from_cents


_HELPER_TEXT = (
    "Dom/mes: To link your Throne, run /register domme in this server.\n"
    "Subs: To link a name you use on Throne, run /register sub."
)


def _line(i: int, label: str) -> str:
    return ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"#{i}"


def leaderboard_card(
    *,
    title: str,
    entries: list[LeaderboardEntry],
    summary: LeaderboardSummary,
    footer: str | None = None,
    status: LeaderboardStatus | str = LeaderboardStatus.LIVE,
) -> RenderedMessage:
    del title, summary

    if not entries:
        entries_text = (
            "No sends have made it onto the board yet.\n\n"
            "Rob is standing here with a clipboard and absolutely nothing to write down."
        )
    else:
        lines: list[str] = []
        for i, entry in enumerate(entries[:10], 1):
            lines.append(
                f"{_line(i, entry.label)} **{entry.label}**\n"
                f"Amount: {format_money_from_cents(entry.total_cents)} · Sends: {entry.send_count}"
            )
        entries_text = "\n\n".join(lines)

    status_text = render_leaderboard_status(status)
    body = f"{entries_text}"

    return render(
        make_card(
            title="Thy Send Leaderboard",
            body=body,
            color=COLOR_LEADERBOARD,
            variant="leaderboard",
            eyebrow=status_text,
            footer=footer or _HELPER_TEXT,
        )
    )


def leaderboard_stats_card(
    summary: LeaderboardSummary,
    entries: list[LeaderboardEntry],
    *,
    maintenance_enabled: bool = False,
    footer: str | None = None,
) -> RenderedMessage:
    if maintenance_enabled:
        body = (
            "Rob is currently under maintenance, so we've paused the send tracker and leaderboard just until he's done.\n\n"
            "Fear not, once the maintenance is over. All untracked sends made during this time will be sent out and the leaderboard will be updated."
        )
        sections: list[CardSection] = []
    else:
        now = int(time.time())
        leader_name = entries[0].label if entries else "Nobody yet"
        leader_amount = format_money_from_cents(entries[0].total_cents if entries else 0)
        body = f"Last updated: <t:{now}:R>"
        sections = [
            CardSection(title="Leader", text=f"{leader_name} — {leader_amount}", inline=True),
            CardSection(title="Dom/mes", text=str(summary.domme_count), inline=True),
            CardSection(title="Sends Tracked", text=str(summary.send_count), inline=True),
            CardSection(title="Total Tracked", text=format_money_from_cents(summary.total_cents), inline=True),
            CardSection(
                title="Unclaimed",
                text=f"{summary.unclaimed_send_count} sends / {format_money_from_cents(summary.unclaimed_total_cents)}",
                inline=True,
            ),
        ]

    return render(
        make_card(
            title="Thy Send Leaderboard | Stats",
            body=body,
            color=COLOR_LEADERBOARD,
            variant="leaderboard",
            sections=sections,
            footer=footer,
        )
    )
