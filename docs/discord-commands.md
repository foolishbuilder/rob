# Discord Commands

Rob keeps Discord commands user-facing and narrow.

## Public/User Commands

- `/register domme`
- `/register sub`
- `/sendrequest`
- `/leaderboard`
- `/report`

## Domme Commands

- `/add`

## Counting Commands

- `/count set {number}`

## Removed/Not Planned

Rob does not expose broad admin dashboards, event control commands, or deployment actions in Discord.

Maintenance mode, queue management, service restarts, database checks, and leaderboard refresh requests should be handled from the backend with `scripts/robctl`.

## Registration Notes

- `/register domme` now checks the configured `domme_role_id` in `guild_settings` at runtime.
- `/register sub` now checks the configured `sub_role_id` in `guild_settings` at runtime.
- If the required role is missing from server config or the user does not have it, Rob denies the command with a Components V2 permission card and an ephemeral response.

## Command Behavior Notes

- `/leaderboard` now responds with **ephemeral personal stats** only (Dom/me and/or Sub sections based on registration).
- Public leaderboard channel messages are updated by the send queue and `robctl leaderboard refresh`, not by `/leaderboard`.
- `/sendrequest` is restricted to users with the configured `sub_role_id` in `guild_settings`.
- `/report` opens a modal for Rob issue reports and requires acknowledgement that the report is about Rob (not member moderation reports).
