from __future__ import annotations

from datetime import datetime, UTC

from rob.database.repositories.models import LeaderboardEntry, LeaderboardSummary, SendRecord
from rob.ui.cards.leaderboard import leaderboard_card, leaderboard_stats_card
from rob.ui.cards.send import send_card
from rob.ui.copy import throne_setup_steps


def _send(sub_name: str | None = None) -> SendRecord:
    return SendRecord(1,1,None,10,None,None,sub_name,1099,"USD",None,"throne","Flowers",None,None,None,None,False,False,datetime.now(UTC),datetime.now(UTC),"pending",None,None,None,datetime.now(UTC))


def test_setup_step_2_contains_almighty_link():
    text = throne_setup_steps("https://example.com/hook")
    assert "The almighty link" in text
    assert "https://example.com/hook" in text


def test_send_card_title_and_flying_dutchman():
    msg = send_card(send=_send(None), domme_label="@Domme", sub_label=None, rank=2)
    contents = "\n".join(str(getattr(ch, "content", "")) for ch in msg.view.children[0].children)
    assert "just got a new send" in contents
    assert "The Flying Dutchman" in contents
    assert "Rob Send ID" not in contents


def test_send_card_unclaimed_sender_copy():
    msg = send_card(send=_send("gifter_name"), domme_label="@Domme", sub_label="gifter_name", rank=None)
    contents = "\n".join(str(getattr(ch, "content", "")) for ch in msg.view.children[0].children)
    assert "gifter_name with no nickname claimed" in contents


def test_leaderboard_main_and_stats_titles_and_separators():
    entries=[LeaderboardEntry("@A",1,12345,7), LeaderboardEntry("@B",2,9000,3), LeaderboardEntry("@C",3,5000,2), LeaderboardEntry("@D",4,2500,1)]
    summary=LeaderboardSummary(29845,13,4,2)
    main=leaderboard_card(title="ignored",entries=entries,summary=summary)
    stats=leaderboard_stats_card(summary, entries)
    main_children = main.view.children[0].children
    stats_children = stats.view.children[0].children
    main_contents = "\n".join(str(getattr(ch, "content", "")) for ch in main_children)
    stats_contents = "\n".join(str(getattr(ch, "content", "")) for ch in stats_children)

    assert [type(child).__name__ for child in main_children] == [
        "TextDisplay",
        "Separator",
        "TextDisplay",
        "Separator",
        "TextDisplay",
        "Separator",
        "TextDisplay",
    ]
    assert "🏆 Thy Send Leaderboard" in main_contents
    assert "🥇" in main_contents and "🥈" in main_contents and "🥉" in main_contents and "#4" in main_contents

    assert [type(child).__name__ for child in stats_children] == ["TextDisplay", "Separator", "TextDisplay"]
    assert "🏆 Thy Send Leaderboard | Stats" in stats_contents
    assert "Leaderboard last updated" in stats_contents
    assert "👑" not in stats_contents and "🦹‍♀️" not in stats_contents and "💸" not in stats_contents


def test_leaderboard_empty_state_uses_same_separator_structure():
    summary = LeaderboardSummary(0, 0, 0, 0)
    main = leaderboard_card(title="ignored", entries=[], summary=summary)
    children = main.view.children[0].children
    assert [type(child).__name__ for child in children] == [
        "TextDisplay",
        "Separator",
        "TextDisplay",
        "Separator",
        "TextDisplay",
        "Separator",
        "TextDisplay",
    ]
    assert "No sends have made it onto the board yet." in children[4].content
