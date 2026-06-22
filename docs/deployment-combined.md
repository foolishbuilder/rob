# Combined single-host deployment

Rob can run as **two services on one host** instead of two separate servers.
The Discord bot and the Throne webhook receiver stay as separate systemd units
and separate `.env` files — they simply talk to each other over loopback
(`127.0.0.1`) instead of a private network. **The PostgreSQL database stays
remote/separate.**

```
        one host
┌───────────────────────────────────────────────┐
│  rob-bot.service        rob-webhook.service     │        ┌────────────┐
│  Discord + ops bridge   Throne receiver         │        │  Postgres  │
│  127.0.0.1:8811  <──────  :8080                 │  ────▶ │  (remote)  │
│        notify: http://127.0.0.1:8811/ops/...    │        └────────────┘
└───────────────────────────────────────────────┘
                 ▲ public Throne webhook URL via cloudflared → 127.0.0.1:8080
```

## Lean co-location (recommended for a single host)

If the bot is already installed at `/opt/rob-bot/app`, the quickest way to add
the webhook is to **reuse the bot's existing checkout and virtualenv** instead
of cloning the repo and building a second venv:

```bash
sudo bash deploy/scripts/install-webhook-on-bot.sh
```

One codebase, one set of dependencies, two systemd services. The webhook runs
the same code the bot already deployed, so a normal `deploy-bot.sh` keeps both
in version lock-step (just `rob restart webhook` afterwards).

The script writes a webhook `.env` **outside** the bot tree (default
`/opt/rob-webhook/.env`, so a bot redeploy's `git clean` can't delete it) and
**derives its values from the bot's `.env`**: it reuses the shared
`ROB_OPS_SECRET` (generating + syncing one if absent), copies `LOG_LEVEL` /
`THRONE_WEBHOOK_BASE_URL`, derives `DATABASE_URL` from the bot's (swapping the
`*_bot` DB user for `*_webhook` and blanking the password), and forces the
loopback wiring (`THRONE_WEBHOOK_HOST=127.0.0.1`,
`ROB_BOT_NOTIFY_URL=http://127.0.0.1:8811/ops/sends/process`). It never copies a
`DISCORD_TOKEN` onto the webhook side.

The webhook DB **password** is the one value it can't derive — set it in
`/opt/rob-webhook/.env`, or supply it up front:

```bash
# Provide the webhook DB URL directly:
sudo bash deploy/scripts/install-webhook-on-bot.sh \
  --webhook-db-url 'postgresql://prod_rob_webhook:REALPASS@HOST:25060/rob_prod?sslmode=require'

# Or import an existing webhook .env (e.g. scp'd from the old webhook host):
sudo bash deploy/scripts/install-webhook-on-bot.sh --from-env /root/old-webhook.env
```

Useful flags: `--dry-run` (show the plan, redacting secrets, write nothing),
`--port N`, `--rotate-secret`, `--no-start`, `--yes`. See `--help` for all of
them. After it runs, finish with steps 4–5 below (public Throne URL + checks).

## Two-app setup (separate clones)

The original model installs the webhook as its own app dir with its own venv —
use this if you want the two fully isolated, or are spreading them across hosts.

1. Install both apps on the host (Debian/Ubuntu):

   ```bash
   sudo bash deploy/scripts/install-bot.sh
   sudo bash deploy/scripts/install-webhook.sh
   ```

   These create `/opt/rob-bot/app` and `/opt/rob-webhook/app`, each with its own
   `.env`.

2. Put the real `DATABASE_URL` (and `DISCORD_TOKEN`) into each `.env`:
   - bot → `prod_rob_bot` user
   - webhook → `prod_rob_webhook` user

3. Run **fix-me** to wire the two services together over loopback:

   ```bash
   sudo bash deploy/scripts/fix-me.sh          # or:  rob fix-me
   ```

   `fix-me` is idempotent and backs up each `.env` before editing. It:
   - sets the bot's `ROB_OPS_HOST=127.0.0.1`, `ROB_OPS_PORT=8811`
   - sets the webhook's `ROB_BOT_NOTIFY_URL=http://127.0.0.1:8811/ops/sends/process`
     and `THRONE_WEBHOOK_HOST=127.0.0.1`
   - generates/propagates a **shared `ROB_OPS_SECRET`** into both files
   - installs + enables both systemd units, runs the DB checks, restarts, and
     hits both `/health` endpoints
   - **never** touches `DATABASE_URL`

   Useful flags: `--dry-run` (show the plan, write nothing), `--rotate-secret`
   (force a fresh shared secret), `--bot-dir` / `--webhook-dir` (non-default
   paths), `--yes` (no prompt).

4. Keep the public Throne webhook URL reaching the local receiver, e.g.
   cloudflared → `http://127.0.0.1:8080` (see
   [`deployment-webhook-dev.md`](deployment-webhook-dev.md)). Do not expose port
   `8080` or `8811` publicly.

5. Check everything any time:

   ```bash
   rob status
   ```

## Leaderboard access role (test guild)

In the test guild, viewing the leaderboard is gated by a role. Holding the role
grants both the `/leaderboard` command and read access to `#leaderboard`.

1. Create a role (e.g. **Leaderboard**) in Discord.
2. Set the `#leaderboard` channel so only that role (and staff) can read it.
3. Give Rob **Manage Roles**, and drag Rob's role **above** the access role in
   Server Settings → Roles, so Rob can assign it.
4. Tell Rob which role it is:

   ```bash
   rob scan            # shows the suggested "Leaderboard Access Role" match
   rob auto-apply roles
   ```

   (or `rob auto-apply leaderboard_view_role_id` for just that field.)

Members then opt in via the Dom/me setup DM or `/preferences`; Rob assigns or
removes the role to match their choice.
