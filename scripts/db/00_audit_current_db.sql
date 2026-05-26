-- Rob DB Audit
-- Run this first, before any ownership/grant/cleanup operations.
-- Recommended: connect as the highest-privilege managed DB admin role (e.g. doadmin).

SELECT current_database();
SELECT current_user;

SELECT datname
FROM pg_database
WHERE datistemplate = false
ORDER BY datname;

SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin
FROM pg_roles
WHERE rolname ILIKE '%rob%' OR rolname ILIKE '%pfaint%'
ORDER BY rolname;

SELECT schemaname, tablename, tableowner
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- This query assumes schema_migrations already exists in the connected DB.
SELECT version, applied_at
FROM schema_migrations
ORDER BY version;
