-- Rob DB Legacy Cleanup (Development)
-- This script intentionally separates analysis, merge, and DROP steps.
-- Review outputs before any destructive operation.

\connect rob_dev

-- ---------------------------------------------------------------------
-- 1) Leaderboard table duplicate analysis (safe if plural table missing)
-- ---------------------------------------------------------------------
DO $$
DECLARE
    singular_rows bigint := 0;
    plural_rows bigint := 0;
    plural_only_rows bigint := 0;
BEGIN
    SELECT COUNT(*) INTO singular_rows FROM leaderboard_message;

    IF to_regclass('public.leaderboard_messages') IS NULL THEN
        RAISE NOTICE 'legacy table public.leaderboard_messages is not present; nothing to merge.';
        RAISE NOTICE 'leaderboard_message rows=%', singular_rows;
        RETURN;
    END IF;

    SELECT COUNT(*) INTO plural_rows FROM leaderboard_messages;
    EXECUTE $q$
        SELECT COUNT(*)
        FROM (
            SELECT *
            FROM leaderboard_messages
            EXCEPT
            SELECT *
            FROM leaderboard_message
        ) diff
    $q$
    INTO plural_only_rows;

    RAISE NOTICE 'leaderboard_message rows=%', singular_rows;
    RAISE NOTICE 'leaderboard_messages rows=%', plural_rows;
    RAISE NOTICE 'rows present only in leaderboard_messages=%', plural_only_rows;
END $$;

-- Merge any rows that do not already exist in the canonical table.
DO $$
BEGIN
    IF to_regclass('public.leaderboard_messages') IS NULL THEN
        RAISE NOTICE 'skip merge: public.leaderboard_messages is not present.';
        RETURN;
    END IF;

    INSERT INTO leaderboard_message (
        guild_id,
        message_key,
        leaderboard_type,
        channel_id,
        message_id,
        created_at,
        updated_at
    )
    SELECT
        guild_id,
        message_key,
        leaderboard_type,
        channel_id,
        message_id,
        created_at,
        updated_at
    FROM leaderboard_messages old
    ON CONFLICT (guild_id, message_key) DO NOTHING;
END $$;

DO $$
DECLARE
    plural_only_rows bigint := 0;
BEGIN
    IF to_regclass('public.leaderboard_messages') IS NULL THEN
        RETURN;
    END IF;
    EXECUTE $q$
        SELECT COUNT(*)
        FROM (
            SELECT *
            FROM leaderboard_messages
            EXCEPT
            SELECT *
            FROM leaderboard_message
        ) diff
    $q$
    INTO plural_only_rows;
    RAISE NOTICE 'rows still present only in leaderboard_messages after merge=%', plural_only_rows;
END $$;

-- ---------------------------------------------------------------------
-- 2) Destructive step (manual): drop legacy plural table only after review
-- ---------------------------------------------------------------------
-- DROP TABLE IF EXISTS leaderboard_messages;

-- ---------------------------------------------------------------------
-- 3) Legacy Throne wishlist table decision
-- ---------------------------------------------------------------------
-- Runtime code no longer uses throne_wishlist_items in Rob v2.
-- Keep for historical audit until you're ready to delete.
--
-- Optional destructive cleanup:
-- DROP TABLE IF EXISTS throne_wishlist_items;
