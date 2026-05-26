-- Rob DB Role Bootstrap
-- Provider note:
-- - Managed PostgreSQL providers (including DigitalOcean) commonly restrict true SUPERUSER.
-- - Use the provider admin role (for example doadmin) to execute this script.
-- - Replace all '<replace_me>' placeholders before running.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pfaint') THEN
        CREATE ROLE pfaint LOGIN PASSWORD '<replace_me>';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rob_dev_migrator') THEN
        CREATE ROLE rob_dev_migrator LOGIN PASSWORD '<replace_me>';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rob_dev_bot') THEN
        CREATE ROLE rob_dev_bot LOGIN PASSWORD '<replace_me>';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rob_dev_webhook') THEN
        CREATE ROLE rob_dev_webhook LOGIN PASSWORD '<replace_me>';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rob_prod_migrator') THEN
        CREATE ROLE rob_prod_migrator LOGIN PASSWORD '<replace_me>';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rob_prod_bot') THEN
        CREATE ROLE rob_prod_bot LOGIN PASSWORD '<replace_me>';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rob_prod_webhook') THEN
        CREATE ROLE rob_prod_webhook LOGIN PASSWORD '<replace_me>';
    END IF;
END $$;

-- Optional/provider-dependent privilege escalation for human admin role.
-- Uncomment only if your managed provider and policy allow it.
-- ALTER ROLE pfaint CREATEDB CREATEROLE;
