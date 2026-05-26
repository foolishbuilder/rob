-- Rob Dev Data Cleanup (manual, optional, destructive)
-- IMPORTANT:
-- - Nothing in this file should run automatically.
-- - Uncomment one section at a time and review before execution.
-- - Intended for rob_dev only.

\connect rob_dev

-- ---------------------------------------------------------------------
-- Option 1: delete test sends already marked as test
-- ---------------------------------------------------------------------
-- DELETE FROM sends
-- WHERE is_test_send = true;

-- ---------------------------------------------------------------------
-- Option 2: delete known Throne test sender records by sub_name
-- ---------------------------------------------------------------------
-- DELETE FROM sends
-- WHERE lower(COALESCE(sub_name, '')) IN ('marie_123');

-- ---------------------------------------------------------------------
-- Option 3: delete failed/ignored sends older than a chosen cutoff
-- Replace interval or hard-coded timestamp as needed.
-- ---------------------------------------------------------------------
-- DELETE FROM sends
-- WHERE discord_post_status IN ('failed', 'ignored')
--   AND created_at < now() - interval '30 days';

-- ---------------------------------------------------------------------
-- Option 4: delete public leaderboard tokens for a specific dev guild
-- Replace <dev_guild_id> with a real value.
-- ---------------------------------------------------------------------
-- DELETE FROM public_leaderboards
-- WHERE guild_id = <dev_guild_id>;
