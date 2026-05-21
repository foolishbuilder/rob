from __future__ import annotations

SUCCESS_FOOTER = "Rob kept the paperwork tidy."
ERROR_FOOTER = "Rob hit a snag, not a meltdown."
MAINTENANCE_FOOTER = "Queued sends will catch up after maintenance."
STATUS_FOOTER = "Professional enough to deploy, opinionated enough to be Rob."
LEADERBOARD_FOOTER = "Tracked from posted sends in PostgreSQL."
COUNTING_FOOTER = "One number at a time. No shortcuts."

DOMME_REGISTERED_TITLE = "You're registered!"
DOMME_REGISTERED_BODY = (
    "Thanks for entrusting Rob with tracking your Throne sends!\n\n"
    "Before we can fully start, there’s just one more thing I need you to do. "
    "In order for Rob to correctly receive your Throne sends, you’ll need to pop a special URL into Throne.\n\n"
    "Because that link is secret, I’ve sent you a DM to help get it sorted."
)

THRONE_SETUP_TITLE = "Throne Tracking Setup!"
THRONE_SETUP_INTRO = (
    "Howdy Partner!\n\n"
    "You've received this DM because you've enabled Throne tracking for yourself. "
    "Before we can continue, we'll need you to do some extra steps inside Throne first."
)


def throne_setup_steps(webhook_url: str) -> str:
    return (
        "To make sure Rob gets the right information, you'll need to set up the Webhook Integration in your Throne settings.\n\n"
        "Here's how:\n\n"
        "1. Head to https://throne.com/ and sign in.\n2. Go to Settings, then click Integrations.\n3. Scroll until you see Webhooks.\n"
        "4. Click Enable Webhooks.\n5. Under Subscriber URLs, click Add URL.\n6. Enter the almighty link below.\n"
        "7. Click Save Settings, then click Test Webhook and wait for the success message.\n\n"
        "Once done, come back here and I'll let you know if it worked.\n\n"
        f"The almighty link:\n```\n{webhook_url}\n```\nDid it work?"
    )
