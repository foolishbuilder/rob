# Discord Commands

## Public commands

- `/register domme` (no options; starts Dom/me DM setup flow and collects Throne profile in modal)
- `/register sub` (no options; opens modal for up to 3 Throne usernames/send names)
- `/leaderboard`
- `/settings mode` (test guild only)
- `/settings summary` (test guild only, private modes)
- `/report`

## Dom/me commands

- `/add`

## Counting commands

- `/count set {number}`

## Inactivity commands

- `/inactivitytest`
- `/inactivelist`

## Moderator prefix commands

- `!rob-blacklist <discord_user_id_or_mention> [reason]`
- `!rob-unblacklist <discord_user_id_or_mention>`
- `!throne-blacklist <discord_user_id_or_mention>`

## Removed in rebuild

- `/sendrequest`
- `/privacy`
- `/broadcast`

## Notes

- Registration role checks are runtime-validated from `vib_settings`.
- During maintenance, `/register domme` and `/register sub` are intentionally unavailable while counting stays active.
- `/leaderboard` is for user-facing stats and should not create schema changes or admin side effects.
- After deploy, Discord command sync removes retired commands. Guild removals usually appear quickly; global command removal can take longer to propagate.
