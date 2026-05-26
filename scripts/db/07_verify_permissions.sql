-- Rob DB Permission and Schema Verification
-- Run this after grants/ownership/cleanup steps.

DO $$
DECLARE
    db_name text := current_database();
    role_prefix text;
    migrator_role text;
    bot_role text;
    webhook_role text;
    missing_count integer;
    table_owner_violations integer;
    runtime_owner_violations integer;
BEGIN
    IF db_name = 'rob_dev' THEN
        role_prefix := 'rob_dev';
    ELSIF db_name = 'rob_prod' THEN
        role_prefix := 'rob_prod';
    ELSE
        RAISE EXCEPTION 'Expected to run against rob_dev or rob_prod. Current database: %', db_name;
    END IF;

    migrator_role := role_prefix || '_migrator';
    bot_role := role_prefix || '_bot';
    webhook_role := role_prefix || '_webhook';

    -- Required roles must exist and be login-capable.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = migrator_role AND rolcanlogin) THEN
        RAISE EXCEPTION 'Missing login role: %', migrator_role;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = bot_role AND rolcanlogin) THEN
        RAISE EXCEPTION 'Missing login role: %', bot_role;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = webhook_role AND rolcanlogin) THEN
        RAISE EXCEPTION 'Missing login role: %', webhook_role;
    END IF;

    -- Required connect grants.
    IF NOT has_database_privilege(migrator_role, db_name, 'CONNECT') THEN
        RAISE EXCEPTION 'Role % is missing CONNECT on %', migrator_role, db_name;
    END IF;
    IF NOT has_database_privilege(bot_role, db_name, 'CONNECT') THEN
        RAISE EXCEPTION 'Role % is missing CONNECT on %', bot_role, db_name;
    END IF;
    IF NOT has_database_privilege(webhook_role, db_name, 'CONNECT') THEN
        RAISE EXCEPTION 'Role % is missing CONNECT on %', webhook_role, db_name;
    END IF;

    -- Required tables must exist.
    SELECT COUNT(*)
    INTO missing_count
    FROM (
        SELECT table_name
        FROM (VALUES
            ('blacklist'),
            ('bot_state'),
            ('counting_state'),
            ('dommes'),
            ('guild_settings'),
            ('leaderboard_message'),
            ('public_leaderboards'),
            ('schema_migrations'),
            ('send_requests'),
            ('sends'),
            ('subs'),
            ('throne_creators')
        ) required(table_name)
        WHERE to_regclass(format('public.%I', table_name)) IS NULL
    ) missing;
    IF missing_count > 0 THEN
        RAISE EXCEPTION 'One or more required tables are missing.';
    END IF;

    -- Required migrations must be present.
    SELECT COUNT(*)
    INTO missing_count
    FROM (
        SELECT version
        FROM (VALUES
            ('001_initial'),
            ('002_fix_schema'),
            ('003_test_send_flag'),
            ('003_throne_setup_verification'),
            ('004_public_send_ids'),
            ('005_leaderboard_message_table_name'),
            ('006_send_request_resolution_and_report_channel'),
            ('007_inactivity_role_id'),
            ('008_public_leaderboards'),
            ('009_domme_public_display_names')
        ) required(version)
        WHERE NOT EXISTS (
            SELECT 1
            FROM schema_migrations sm
            WHERE sm.version = required.version
        )
    ) missing_versions;
    IF missing_count > 0 THEN
        RAISE EXCEPTION 'One or more required migrations are not recorded in schema_migrations.';
    END IF;

    -- Legacy duplicate table should not remain after cleanup.
    IF to_regclass('public.leaderboard_messages') IS NOT NULL THEN
        RAISE EXCEPTION 'Legacy table public.leaderboard_messages still exists. Run cleanup script.';
    END IF;

    -- Runtime users must not own app tables.
    SELECT COUNT(*)
    INTO runtime_owner_violations
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tableowner IN (bot_role, webhook_role);
    IF runtime_owner_violations > 0 THEN
        RAISE EXCEPTION 'Runtime roles own public tables. Ownership must remain with migrator.';
    END IF;

    -- Managed-provider admin role should not own app tables once ownership transfer is complete.
    SELECT COUNT(*)
    INTO table_owner_violations
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tableowner = 'doadmin';
    IF table_owner_violations > 0 THEN
        RAISE EXCEPTION 'One or more app tables are still owned by doadmin.';
    END IF;

    -- Webhook should not hold DELETE on sends.
    IF has_table_privilege(webhook_role, 'public.sends', 'DELETE') THEN
        RAISE EXCEPTION 'Role % should not have DELETE on public.sends', webhook_role;
    END IF;
END $$;

-- Optional readout for manual auditing:
SELECT schemaname, tablename, tableowner
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
