from __future__ import annotations

from datetime import datetime, timezone

from rob.database.repositories.models import SendRecord
from rob.services.send_display import build_sub_display


def _send(sub_name: str | None, *, sub_user_id: int | None = None) -> SendRecord:
    now = datetime.now(timezone.utc)
    return SendRecord(
        1,
        1,
        None,
        10,
        None,
        sub_user_id,
        sub_name,
        1099,
        "USD",
        None,
        "throne_webhook",
        "Flowers",
        None,
        None,
        None,
        None,
        False,
        False,
        now,
        now,
        "posted",
        None,
        None,
        None,
        now,
    )


def test_anonymous_sender_displays_secret_admirer():
    assert build_sub_display(_send("Anonymous")) == "a secret admirer"


def test_known_test_sender_displays_throne_test_user():
    assert build_sub_display(_send("marie_123"), test_gifter_usernames=("marie_123",)) == "Throne's Test User"


def test_registered_sub_displays_discord_mention():
    assert build_sub_display(_send("gifter_name", sub_user_id=123)) == "<@123>"


def test_unclaimed_named_sender_displays_claim_hint():
    assert build_sub_display(_send("gifter_name")) == "gifter_name with no nickname claimed"


def test_missing_sender_displays_generic_unclaimed_copy():
    assert build_sub_display(_send(None)) == "Sub with no nickname claimed"
