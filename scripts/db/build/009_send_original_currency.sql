-- Migration 009: Add original_amount_cents and original_currency to sends.
-- Tracks the pre-conversion amount for non-USD sends.

ALTER TABLE sends
    ADD COLUMN IF NOT EXISTS original_amount_cents INTEGER;

ALTER TABLE sends
    ADD COLUMN IF NOT EXISTS original_currency TEXT;

INSERT INTO db_build_version (version, notes)
VALUES ('009_send_original_currency', 'Add original_amount_cents and original_currency to sends')
ON CONFLICT (version) DO NOTHING;
