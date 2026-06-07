# Bot Server

The bot server is the Discord-only side of Rob.

## Responsibilities

- Connects to Discord.
- Connects to PostgreSQL.
- Accepts send notifications from the webhook through the private bot ops bridge.
- Processes the specific recorded send immediately instead of constantly polling pending sends.
- Releases `queued_maintenance` sends after maintenance is disabled.
- Posts send notifications to the configured tracking channel.
- Refreshes leaderboard messages from posted sends.
- Ignores imported legacy sends that were already marked `posted`.
- Handles `/register`, `/leaderboard`, `/add`, and `/count set`.
- Runs the counting listener.

## Runtime

- Entry point: `python -m apps.bot.main`
- Background worker: `rob.services.send_queue_service.SendQueueService`
- PostgreSQL is the source of truth for queue state and maintenance state.
- The queue worker processes send IDs pushed by the webhook and only uses slow fallback checks for maintenance/ops requests.

## Required environment

- `APP_ENV`
- `LOG_LEVEL`
- `DATABASE_URL`
- `DISCORD_TOKEN`
- `BOT_NAME`
- `ROB_OPS_HOST`
- `ROB_OPS_PORT`
- `ROB_OPS_SECRET`

The bot does not host the Throne webhook HTTP server.

If age verification is enabled on the bot, also set:

- `ROB_BACKEND_URL`
- `ROB_BACKEND_SECRET`
- `ROB_AGE_VERIFICATION_ENABLED=true`
- `ROB_AGE_VERIFICATION_TEST_ONLY=true`
- `ROB_AGE_VERIFIED_ROLE_ID`

## Age verification backend

Rob's age-verification bot commands do not talk to Discord-only code. They call
the webhook/backend service over HTTP.

Important:

- There is no separate `age` Python service to deploy.
- The existing webhook app already serves:
  - `POST /age-verification/start`
  - `GET /age-verification/status`
  - `POST /yoti/notification`
  - `GET /yoti/callback`

### Quickest working setup

Reuse the existing webhook hostname:

```env
ROB_BACKEND_URL=https://throne.robthebot.com
ROB_BACKEND_SECRET=<same secret as webhook host>
ROB_AGE_VERIFICATION_ENABLED=true
ROB_AGE_VERIFICATION_TEST_ONLY=true
ROB_AGE_VERIFIED_ROLE_ID=<test guild 18+ role id>
```

This works because the webhook host already fronts the age-verification routes.

### Optional dedicated hostname

If you want `https://age.robthebot.com`, point that hostname at the same
Cloudflare tunnel/origin as `https://throne.robthebot.com`, then update:

```env
ROB_BACKEND_URL=https://age.robthebot.com
```

The webhook host must also use the same public base for Yoti callbacks, for
example:

```env
YOTI_PUBLIC_BASE_URL=https://age.robthebot.com
```

If `ROB_BACKEND_URL` points at a hostname that does not resolve yet, the bot
will fail with a DNS/connect error before it ever reaches Yoti.

## Runtime verification

Run this on the bot host after editing `.env` or after a deploy:

```bash
sudo bash deploy/scripts/check-bot-runtime.sh
```

It validates the parsed bot settings, DB grants/schema, systemd state, the
local bot-ops health endpoint, and `ROB_BACKEND_URL` reachability when set.

## Webhook-to-bot send notifications

The bot ops bridge listens on `ROB_OPS_HOST:ROB_OPS_PORT`, usually `127.0.0.1:8811`.
Because that address is local to the bot server, the webhook server cannot reach it unless the bot server exposes a small, protected reverse proxy route.

Recommended Nginx route on `bot-01.robthebot.com`:

```nginx
location = /ops/sends/process {
    proxy_pass http://127.0.0.1:8811/ops/sends/process;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Keep the bot ops bridge itself bound to `127.0.0.1`. Do not open port `8811` publicly.
The webhook must send the matching `ROB_OPS_SECRET` header through `ROB_BOT_NOTIFY_URL`.
