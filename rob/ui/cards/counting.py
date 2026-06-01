from __future__ import annotations

from rob.ui.components import make_card, render
from rob.ui.render import CardSection, RenderedMessage
from rob.ui.theme import COLOR_DANGER, COLOR_INFO, COLOR_SUCCESS, COLOR_WARNING


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
            variant="success",
        )
    )


def counting_same_user_reminder_card() -> RenderedMessage:
    return render(
        make_card(
            title="Hold up there, speedy.",
            body=(
                "One number per person at a time.\n"
                "Let someone else have a go before you count again."
            ),
            color=COLOR_WARNING,
            variant="warning",
        )
    )


def count_rescue_needed_card(*, remaining_seconds: int, deadline_unix: int) -> RenderedMessage:
    return count_rescue_needed_for_role_card(
        remaining_seconds=remaining_seconds,
        deadline_unix=deadline_unix,
        failed_user_role="sub",
        claimed_restriction=False,
        claimed_unresolved=False,
    )


def count_rescue_needed_for_role_card(
    *,
    remaining_seconds: int,
    deadline_unix: int,
    failed_user_role: str,
    claimed_restriction: bool,
    claimed_unresolved: bool,
) -> RenderedMessage:
    remaining_seconds = max(0, remaining_seconds)
    minutes, seconds = divmod(remaining_seconds, 60)
    if failed_user_role == "domme":
        opener = "A Dom/me fumbled the count. Subs have 5 minutes to send to them and save it."
    else:
        opener = "A Sub fumbled the count. They have 5 minutes to send and save themselves."
    claim_line = ""
    if failed_user_role == "sub" and claimed_restriction:
        claim_line = "Because you are claimed, the recovery send must go to your Dom/me.\n\n"
    if failed_user_role == "sub" and claimed_unresolved:
        claim_line = (
            "Because your claimed Dom/me could not be resolved, staff should review your claim role before retrying.\n\n"
        )
    body = (
        "The count is wobbling.\n"
        f"{opener}\n\n"
        f"{claim_line}"
        f"**{minutes}m {seconds:02d}s** remaining · Deadline: <t:{deadline_unix}:R>"
    )
    return render(
        make_card(
            title="Count Rescue Needed",
            body=body,
            color=COLOR_WARNING,
            variant="warning",
            footer=f"Deadline: <t:{deadline_unix}:f>",
        )
    )


def count_saved_card(*, next_number: int) -> RenderedMessage:
    return render(
        make_card(
            title="Count Saved",
            body=(
                "Rob saw the send and duct-taped the count back together.\n"
                f"Continue from **{next_number}**."
            ),
            color=COLOR_SUCCESS,
            variant="success",
        )
    )


def count_failed_card() -> RenderedMessage:
    return count_failed_reset_card()


def count_failed_reset_card() -> RenderedMessage:
    return render(
        make_card(
            title="Count Failed",
            body=(
                "No qualifying send arrived in time.\n"
                "Rob has reset the count to **1**."
            ),
            color=COLOR_DANGER,
            variant="danger",
            footer="Better luck next time.",
        )
    )


def count_failed_sub_blocked_card(*, blocked_until_unix: int) -> RenderedMessage:
    return render(
        make_card(
            title="Count Failed",
            body=(
                "No recovery send was detected.\n"
                "You fumbled the count and missed the recovery window, so you are blocked from counting for 12 hours.\n\n"
                f"You can count again: **<t:{blocked_until_unix}:R>**"
            ),
            color=COLOR_DANGER,
            variant="danger",
        )
    )


def count_blocked_sub_card(*, blocked_until_unix: int) -> RenderedMessage:
    return render(
        make_card(
            title="Count Blocked",
            body=(
                "You fumbled the count and missed the recovery window, so you are blocked from counting for 12 hours.\n\n"
                f"You can count again: **<t:{blocked_until_unix}:R>**"
            ),
            color=COLOR_DANGER,
            variant="danger",
        )
    )
