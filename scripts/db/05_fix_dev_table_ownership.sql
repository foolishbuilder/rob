-- Rob DB Ownership Repair (Development)
-- Goal: move dev schema object ownership to rob_dev_migrator.
-- Run as a role that currently owns objects or has enough rights (often doadmin).

\connect rob_dev

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'blacklist',
        'bot_state',
        'counting_state',
        'dommes',
        'guild_settings',
        'leaderboard_message',
        'leaderboard_messages',
        'public_leaderboards',
        'schema_migrations',
        'send_requests',
        'sends',
        'subs',
        'throne_creators',
        'throne_wishlist_items'
    ]
    LOOP
        IF to_regclass(format('public.%I', table_name)) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I OWNER TO rob_dev_migrator', table_name);
        END IF;
    END LOOP;
END $$;

DO $$
DECLARE
    sequence_name text;
BEGIN
    FOREACH sequence_name IN ARRAY ARRAY[
        'dommes_id_seq',
        'subs_id_seq',
        'throne_creators_id_seq',
        'sends_id_seq',
        'send_requests_id_seq',
        'leaderboard_message_id_seq',
        'public_leaderboards_id_seq'
    ]
    LOOP
        IF to_regclass(format('public.%I', sequence_name)) IS NOT NULL THEN
            EXECUTE format('ALTER SEQUENCE public.%I OWNER TO rob_dev_migrator', sequence_name);
        END IF;
    END LOOP;
END $$;

-- Migration 009 repair:
-- Only run this record repair when dommes already has the expected columns.
DO $$
DECLARE
    has_display_name boolean;
    has_display_name_updated_at boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'dommes'
          AND column_name = 'public_display_name'
    ) INTO has_display_name;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'dommes'
          AND column_name = 'public_display_name_updated_at'
    ) INTO has_display_name_updated_at;

    IF has_display_name AND has_display_name_updated_at THEN
        INSERT INTO schema_migrations (version, applied_at)
        VALUES ('009_domme_public_display_names', now())
        ON CONFLICT (version) DO NOTHING;
    ELSE
        RAISE EXCEPTION
            'Cannot mark 009_domme_public_display_names as applied because dommes columns are missing.';
    END IF;
END $$;
