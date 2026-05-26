# Database Architecture (Dev + Prod)

## Target databases

- `rob_dev`
- `rob_prod`

Do not use `defaultdb` or `_dodb` for Rob application data.

## Target roles

- Human/admin: `pfaint`
- Dev migration owner: `rob_dev_migrator`
- Dev runtime bot: `rob_dev_bot`
- Dev runtime webhook: `rob_dev_webhook`
- Prod migration owner: `rob_prod_migrator`
- Prod runtime bot: `rob_prod_bot`
- Prod runtime webhook: `rob_prod_webhook`

## Service to DB user mapping

- Bot service (dev): `DATABASE_URL -> rob_dev_bot@rob_dev`
- Webhook service (dev): `DATABASE_URL -> rob_dev_webhook@rob_dev`
- Migrations (dev): `MIGRATION_DATABASE_URL -> rob_dev_migrator@rob_dev`
- Bot service (prod): `DATABASE_URL -> rob_prod_bot@rob_prod`
- Webhook service (prod): `DATABASE_URL -> rob_prod_webhook@rob_prod`
- Migrations (prod): `MIGRATION_DATABASE_URL -> rob_prod_migrator@rob_prod`

## Role responsibilities

- `*_migrator`:
  - Own schema objects.
  - Execute migrations.
  - May create/alter/drop schema objects.
- `*_bot`:
  - Runtime read/write for bot features.
  - Must not own tables/sequences.
  - Must not run migrations.
- `*_webhook`:
  - Runtime read/write only for webhook ingestion and related reads.
  - Narrower grants than bot (no destructive deletes by default).
  - Must not own tables/sequences.

## Ownership and privileges model

- Ownership should converge on `rob_dev_migrator` in dev and `rob_prod_migrator` in prod.
- Runtime users receive only grants required for normal operation.
- Default privileges are configured for migrator-created future objects so runtime grants stay consistent after new migrations.

## Legacy table handling

- Canonical leaderboard table: `leaderboard_message`.
- Legacy duplicate: `leaderboard_messages` (must be merged then dropped manually).
- Legacy wishlist table: `throne_wishlist_items` is deprecated in v2 runtime and can be dropped after manual review.

## Migration recording integrity

`009_domme_public_display_names` must be present in `schema_migrations` once its columns exist in `dommes`. If columns already exist but migration row is missing, repair by inserting the migration record explicitly.

## Managed PostgreSQL limitations (DigitalOcean)

- Do not assume superuser access is available.
- Use provider admin role (for example `doadmin`) for bootstrap operations.
- `pfaint` should be granted the highest practical privileges allowed by policy/provider.

## Backup and restore notes

- Treat `rob_prod` as authoritative; keep routine managed backups/snapshots enabled.
- Validate restore procedures into a non-production target before major migrations.
- Never seed production by cloning dev test data by default.

## Migration process

1. Set runtime `DATABASE_URL` for service.
2. Set `MIGRATION_DATABASE_URL` for migrator role.
3. Run `scripts/run_migrations.py` (uses `MIGRATION_DATABASE_URL` when present).
4. Run `scripts/check_db.py` using runtime credentials.
5. Start/restart services.
