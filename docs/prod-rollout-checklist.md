# Production Rollout Checklist

## 1) Create production roles

- Run `scripts/db/01_create_roles.sql` as provider admin role.
- Confirm `rob_prod_migrator`, `rob_prod_bot`, and `rob_prod_webhook` exist and can login.

## 2) Create `rob_prod`

- Run `scripts/db/02_create_databases.sql`.
- Confirm `rob_prod` exists and owner is `rob_prod_migrator`.

## 3) Run migrations on `rob_prod`

- Export:
  - `MIGRATION_DATABASE_URL=postgresql://rob_prod_migrator:.../rob_prod?...`
- Execute:
  - `PYTHONPATH=. python -m scripts.run_migrations`

## 4) Apply prod grants

- Run `scripts/db/04_grant_prod_permissions.sql`.
- Ensure runtime users do not have schema-creation privileges.

## 5) Seed minimum production configuration

- Seed only required production values:
  - `guild_settings` rows for production guild(s)
  - required `bot_state` defaults (if applicable)
- Do **not** import dev/test sends by default.

## 6) Configure production env files

- Bot runtime `DATABASE_URL` must use `rob_prod_bot`.
- Webhook runtime `DATABASE_URL` must use `rob_prod_webhook`.
- Migration tasks must use `MIGRATION_DATABASE_URL` with `rob_prod_migrator`.

## 7) Run DB verification

- Run:
  - `PYTHONPATH=. python -m scripts.check_db`
- Address any migration/column/permission warnings before service start.

## 8) Start webhook service

- Start/restart webhook process with prod env.
- Confirm webhook health and DB connectivity.

## 9) Start bot service

- Start/restart bot process with prod env.
- Confirm slash command sync and DB connectivity.

## 10) Verify Discord commands

- Registration commands
- Send request flow
- Leaderboard stats flow
- Counting flow

## 11) Verify Throne webhook ingestion

- Send a controlled test event.
- Confirm event appears in logs and expected tables.

## 12) Verify public leaderboard token flow (if enabled)

- Confirm `public_leaderboards` rows resolve correctly.
- Confirm no `leaderboard_messages` legacy table usage remains.

## 13) Verify logs and alerts

- Bot logs clean of DB permission errors.
- Webhook logs clean of DB permission errors.
- Queue/maintenance/leaderboard updates behaving as expected.

## Optional automation

For a controlled one-time automation path, use:

- `.github/workflows/db-one-time-bootstrap.yml`

This workflow is manual-only (`workflow_dispatch`), confirmation-gated, and expects DB URL secrets to be configured before execution.
