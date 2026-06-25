# Activity / inactive-role system & hourly server backups

Two systems, both **scoped to the test guild** for now (gated on
`rob.config.guilds.TEST_GUILD_ID`). Promote to the main guild later by widening
that gate. Both stay dormant until their roles/channels are configured and the
system is switched on per guild.

## 1. Configure roles & channels (via `rob scan`)

Both systems read their roles/channel from `vib_settings`. `rob guild scan`
(friendly: `rob scan`) discovers them by name and prints the commands to set
them; `rob auto-apply` applies the suggestions.

New scan fields:

| Field | Purpose |
| --- | --- |
| `active_role_id` | Held by verified, recently-active members. |
| `inactive_role_id` | Given when a member goes inactive. |
| `unverified_role_id` | Members who have not verified yet (parked as inactive). |
| `mod_role_id` | Pinged on / can approve backup changes. |
| `trial_mod_role_id` | Pinged on / can approve backup changes. |
| `backup_approval_channel_id` | Where backup approval prompts are posted. |

```bash
rob scan --guild <guild_id>            # review current + suggested mappings
rob auto-apply --guild <guild_id> roles
rob auto-apply --guild <guild_id> backup_approval_channel_id
# or set explicitly:
rob guild set-role    --guild-id <guild_id> --field active_role_id --role-id <id>
rob guild set-channel --guild-id <guild_id> --field backup_approval_channel_id --channel-id <id>
```

## 2. Activity / inactive-role system

Rob records activity (messages, reactions, slash/button interactions) into
`activity:{guild}:user:{uid}:last_active` **in real time, on every event** — and
if the member was marked inactive, they are restored to Active immediately (no
waiting for the next sweep).

Detecting the *absence* of activity isn't event-driven, so a periodic **sweep**
flags newly-inactive members. It runs every `INACTIVITY_LOOP_MINUTES`
(**default weekly = 10080**) and once on each restart. Each sweep:

- **Active** (interacted within `INACTIVITY_INACTIVE_AFTER_DAYS`, default 7):
  keeps the Active role, loses the Inactive role, clears any countdown.
- **Inactive** (no activity for a week): loses the Active role, gains the
  Inactive role, goes on the `inactive_users` countdown, and gets a first DM
  notice. A final notice goes out `INACTIVITY_FINAL_NOTICE_DAYS` (default 7)
  before removal, and the member is kicked once the countdown
  (`INACTIVITY_KICK_GRACE_DAYS`, default 14 → ~3 weeks total) expires. With the
  weekly cadence these stages land on consecutive weekly sweeps.
- **Unverified** (holds `unverified_role_id`): parked as inactive (Inactive role
  on, Active off) but **never** on the kick countdown. Verifying counts as
  activity and restores the Active role.

The first run after enabling uses `INACTIVITY_BOOTSTRAP_GRACE_DAYS` (default 21)
so nobody is kicked the moment the system turns on. Maintenance mode suppresses
DMs and kicks. Both `active_role_id` and `inactive_role_id` must be set or the
system no-ops.

```bash
rob inactivity status --guild <guild_id>
rob inactivity on  --guild <guild_id>
rob inactivity off --guild <guild_id>
```

Mod slash commands (test guild): `/inactivelist` (lists **everyone holding the
Inactive role** with the time until each is kicked, soonest first; parked members
with no scheduled removal are shown last) and `/inactivitytest` (DMs you the
notice templates).

## 3. Hourly server-backup system

Every `SERVER_BACKUP_LOOP_MINUTES` (default 60) Rob snapshots roles, channels,
and core server settings into `server_backups` and diffs against the last
baseline:

- **No changes** → nothing stored (the baseline still represents the guild).
- **Minor edits** (renames, reorders, colours, topics, slowmode) → stored as the
  new baseline.
- **Major change** (deleted/created role or channel, changed role permissions,
  changed channel permission overwrites, or a security-relevant server setting)
  → backups pause and Rob posts a **`### Major Server Change Detected!`** prompt
  to `backup_approval_channel_id`, pinging the mod + trial-mod roles. Backups
  resume only after `SERVER_BACKUP_REQUIRED_APPROVALS` (default 2) **distinct**
  moderators approve, at which point the pending snapshot becomes the new
  baseline. A rejected change keeps the old baseline and is not re-prompted
  until the configuration changes again.

> The prompt carries the warning: **DO NOT ACCEPT THIS IF YOU ARE DOING A REVAMP
> UNLESS YOU ARE SURE EVERYTHING CURRENTLY WORKS.** Approving blesses the current
> structure as the restore point.

If no approval channel is configured, Rob cannot gate a change, so it logs a
warning and adopts the snapshot rather than pausing backups forever.

```bash
rob backup status --guild <guild_id>
rob backup on  --guild <guild_id>
rob backup off --guild <guild_id>
rob backup run --guild <guild_id>   # run one cycle now (via the running bot)
```

## Database

Run the build scripts (`scripts/db/build/012_inactivity_backup_settings.sql`,
`013_server_backups.sql`) and then the relevant grants file. See
`scripts/db/build/README.md`.
