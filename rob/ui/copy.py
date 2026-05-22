from __future__ import annotations

SUCCESS_FOOTER = "Rob kept the paperwork tidy."
ERROR_FOOTER = "In Pat we *somewhat* trust."
WEBHOOK_ERROR_FOOTER = "Pris here."
PERMISSION_ERROR_FOOTER = "Rob is helpful, unfortunately."
DM_FAILED_FOOTER = "Rob brought the envelope. Discord ate it."
SETUP_RENDER_ERROR_FOOTER = "The paperwork fought back."
MAINTENANCE_FOOTER = "Please do not tap the glass."
OFFLINE_FOOTER = "Powered by vibes and consequences."
LEADERBOARD_FOOTER = "Powered by vibes and PostgreSQL."
STATUS_FOOTER = "Professional enough to deploy, opinionated enough to be Rob."
COUNTING_FOOTER = "Rob handled the maths. Somehow."

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
        "As my telekinesis skills are a little rusty, we just need to do one final step to help make sure I get told when sends come through. Here's how:\n\n"
        "1. Head to https://throne.com/ and sign in.\n"
        "2. Go to Settings, then click Integrations.\n"
        "3. Scroll until you see Webhooks.\n"
        "4. Click Enable Webhooks.\n"
        "5. Under Subscriber URLs, click Add URL.\n"
        "6. Enter the almighty link below.\n"
        "7. Click Save Settings, then click Test Webhook and wait for the success message.\n\n"
        "Once done, pop back here to see if Rob picked up your send. I'll update this message if it worked.\n\n"
        f"The almighty link:\n```\n{webhook_url}\n```"
    )
