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
PERMISSION_ROLE_NOT_CONFIGURED = (
    "Rob checked the little permission clipboard, but this server has not configured the required role yet."
)
PERMISSION_ROLE_MISSING = (
    "Rob checked the little permission clipboard and your name was not on it."
)

DOMME_REGISTERED_TITLE = "You're registered!"
DOMME_REGISTERED_BODY = (
    "You are all set.\n\n"
    "Rob has got you registered and your Throne is linked up. Sends will start coming through automatically.\n\n"
    "A link has been sent to your DMs. Pop it into Throne and Rob will take care of the rest.\n\n"
    "-# Need to change anything later? Use /settings anytime."
)

THRONE_SETUP_TITLE = "Throne Tracking Setup!"
WEBHOOK_REISSUE_TITLE = "Action Needed | Rob Upgrade"
WEBHOOK_REFRESH_TITLE = "Rob | New Throne Tracking URL"


def throne_setup_steps(webhook_url: str) -> str:
    return (
        "Hey! Rob here.\n\n"
        "You just got set up with Throne tracking, which means Rob will keep an eye on your sends and make sure everything gets logged properly.\n\n"
        "There is just one small thing to do first. Rob needs a special link added to Throne so he knows when sends come through. Here is how:\n\n"
        "1. Head to throne.com and sign in.\n"
        "2. Go to Settings, then Integrations, then Webhooks.\n"
        "3. Click Enable Webhooks.\n"
        "4. Under Subscriber URLs click Add URL.\n"
        "5. Paste the link below.\n"
        "6. Hit Save Settings then Test Webhook.\n\n"
        "Once Throne confirms it worked head back to the server and let Rob know. He will be waiting.\n\n"
        f"{webhook_url}\n\n"
        "-# Automated message from Rob. No need to reply."
    )


def webhook_refresh_message(webhook_url: str) -> str:
    return (
        "Hey, Rob here with a quick heads up.\n\n"
        "Your Throne tracking link has been refreshed. The old one will not work anymore so you will need to swap it out.\n\n"
        "Go to Settings, then Integrations, then Webhooks in Throne. Replace the old link with this one and hit Save Settings and Test Webhook.\n\n"
        f"{webhook_url}\n\n"
        "Once that is done you are all good. Rob will pick right back up where he left off.\n\n"
        "-# Automated message from Rob. No need to reply."
    )


def webhook_upgrade_message(*, throne_name: str, webhook_url: str) -> str:
    return (
        f"Hey {throne_name},\n\n"
        "You're marked as one of the awesome people who use the Automatic Throne Tracking provided by Rob. "
        "As part of the Rob upgrade, the links used for this tracking have been changed.\n\n"
        "Your old link looking like `https://rob.barecoding.com` will now be changed to:\n\n"
        f"`{webhook_url}`\n\n"
        "Once done, click Save Settings and Test Webhook.\n\n"
        "---\n"
        "-# This is automated! Have a spectacular day!\n\n"
        "When Throne confirms it worked, press **Yes** below so Rob can finish the reconnect."
    )
