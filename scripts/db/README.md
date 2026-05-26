# Rob Database Admin Scripts

These scripts are for manual database administration (dev/prod separation, roles, grants, ownership, and cleanup). They are intentionally explicit and do **not** run automatically from app startup.

## Script order

1. `00_audit_current_db.sql`
2. `01_create_roles.sql`
3. `02_create_databases.sql`
4. Run migrations with the migrator role (`scripts/run_migrations.py` with `MIGRATION_DATABASE_URL`)
5. `03_grant_dev_permissions.sql`
6. `04_grant_prod_permissions.sql`
7. `05_fix_dev_table_ownership.sql` (dev repair path)
8. `06_cleanup_legacy_tables.sql` (manual review + optional DROP steps)
9. `07_verify_permissions.sql`

Optional:
- `cleanup_dev_data.sql`

## Optional one-time GitHub Actions runner

A manual workflow exists at:

- `.github/workflows/db-one-time-bootstrap.yml`

It is intended for a controlled one-time rollout and requires explicit confirmation text.

Required repository secrets:

- `ROB_DB_ADMIN_DATABASE_URL`

Optional runtime-check secrets:

- `ROB_DEV_BOT_DATABASE_URL`
- `ROB_DEV_WEBHOOK_DATABASE_URL`
- `ROB_PROD_BOT_DATABASE_URL`
- `ROB_PROD_WEBHOOK_DATABASE_URL`

Recommended process:

1. Run it manually from the Actions tab (`workflow_dispatch`).
2. Keep `run_create_roles=false` unless you have edited role passwords in `01_create_roles.sql`.
3. Keep `apply_prod=false` for the first dry run unless you are ready.
4. Remove or disable the workflow after the one-time rollout.

## Managed PostgreSQL note (DigitalOcean)

Managed PostgreSQL typically restricts true superuser access. Use the provider admin role (for example `doadmin`) for bootstrap/ownership operations, and treat this as the highest practical privilege role.

## Safety notes

- Replace all password placeholders before applying role scripts.
- Destructive commands are commented out and require explicit manual uncommenting.
- `06_cleanup_legacy_tables.sql` intentionally requires human review before dropping any legacy table.
