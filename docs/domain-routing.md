# Domain Routing

Canonical hostnames:

- `bot-01.robthebot.com`
- `webhook-01.robthebot.com`
- `db-01.robthebot.com`
- `throne.robthebot.com`
- `age.robthebot.com`
- `leaderboard.robthebot.com`

Preferred public webhook route:

- `https://throne.robthebot.com/webhook/{creator_id}/{secret}`

Compatibility webhook route (still supported):

- `https://throne.robthebot.com/throne/webhook/{creator_id}/{secret}`

Future public leaderboard route:

- `https://leaderboard.robthebot.com/guild/{guild_id}`

Age-verification backend route:

- Quickest setup: `https://throne.robthebot.com/age-verification/start`
- Optional dedicated host: `https://age.robthebot.com/age-verification/start`

## Cloudflare guidance

- Prefer Cloudflare Tunnel for:
  - `throne.robthebot.com`
  - `age.robthebot.com`
  - `leaderboard.robthebot.com`
- DNS-only is usually right for SSH/admin identity hostnames:
  - `bot-01.robthebot.com`
  - `webhook-01.robthebot.com`

`db-01.robthebot.com` should remain private/internal/admin-only.
Do not expose PostgreSQL publicly.

Webhook origin should stay local:

- `http://127.0.0.1:8080`

Both `throne.robthebot.com` and optional `age.robthebot.com` should point to
that same local webhook origin if age verification is enabled.

Do not open port `8080` publicly.
