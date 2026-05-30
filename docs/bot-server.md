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
