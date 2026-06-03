ALTER TABLE dommes
ADD COLUMN IF NOT EXISTS notification_mode TEXT NOT NULL DEFAULT 'public';

ALTER TABLE dommes
ADD COLUMN IF NOT EXISTS summary_cadence TEXT DEFAULT 'weekly';

ALTER TABLE dommes
ADD COLUMN IF NOT EXISTS last_summary_sent_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'dommes_notification_mode_check'
    ) THEN
        ALTER TABLE dommes
        ADD CONSTRAINT dommes_notification_mode_check
        CHECK (notification_mode IN ('public', 'private', 'private_leaderboard'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'dommes_summary_cadence_check'
    ) THEN
        ALTER TABLE dommes
        ADD CONSTRAINT dommes_summary_cadence_check
        CHECK (summary_cadence IN ('weekly', 'fortnightly', 'monthly') OR summary_cadence IS NULL);
    END IF;
END $$;

INSERT INTO db_build_version (version, notes)
VALUES ('008_notification_modes', 'Dom/me notification and summary cadence modes')
ON CONFLICT (version) DO NOTHING;
