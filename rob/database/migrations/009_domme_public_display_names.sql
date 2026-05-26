ALTER TABLE dommes
ADD COLUMN IF NOT EXISTS public_display_name TEXT,
ADD COLUMN IF NOT EXISTS public_display_name_updated_at TIMESTAMPTZ;
