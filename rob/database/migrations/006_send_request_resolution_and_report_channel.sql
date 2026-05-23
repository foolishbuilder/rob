ALTER TABLE guild_settings
ADD COLUMN IF NOT EXISTS report_channel_id BIGINT;

ALTER TABLE send_requests
ADD COLUMN IF NOT EXISTS denial_reason TEXT;

ALTER TABLE send_requests
ADD COLUMN IF NOT EXISTS resolved_by_user_id BIGINT;
