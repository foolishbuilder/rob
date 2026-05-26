-- Rob DB Database Bootstrap
-- This file uses psql meta-commands (\gexec), so run with psql:
--   psql "$ADMIN_DATABASE_URL" -f scripts/db/02_create_databases.sql
--
-- This script is non-destructive:
-- - it will create rob_dev / rob_prod only if missing;
-- - it will not drop or recreate existing databases.

SELECT 'CREATE DATABASE rob_dev OWNER rob_dev_migrator'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_database
    WHERE datname = 'rob_dev'
)
\gexec

SELECT 'CREATE DATABASE rob_prod OWNER rob_prod_migrator'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_database
    WHERE datname = 'rob_prod'
)
\gexec

-- Optional visibility check
SELECT datname
FROM pg_database
WHERE datname IN ('rob_dev', 'rob_prod')
ORDER BY datname;
