-- Migration 008: Add main_chat_channel_id to vib_settings
-- Used as the destination for leader change notifications.

ALTER TABLE vib_settings
    ADD COLUMN IF NOT EXISTS main_chat_channel_id BIGINT;

INSERT INTO db_build_version (version, notes)
VALUES ('008_main_chat_channel', 'Add main_chat_channel_id to vib_settings')
ON CONFLICT (version) DO NOTHING;
