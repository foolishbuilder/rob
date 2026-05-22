# Backend Commands

Use [`scripts/robctl`](../scripts/robctl) from the server checkout, or install a shell alias that points to it.

## Supported commands

```bash
scripts/robctl status
scripts/robctl logs bot
scripts/robctl logs webhook
scripts/robctl restart bot
scripts/robctl restart webhook
scripts/robctl restart all

scripts/robctl maintenance status
scripts/robctl maintenance on "Deploying schema changes"
scripts/robctl maintenance off

scripts/robctl queue status
scripts/robctl queue flush

scripts/robctl leaderboard refresh

scripts/robctl count status
scripts/robctl count set 123
```

## Notes

- `maintenance on/off`, `queue status`, `queue flush`, `leaderboard refresh`, and `count` commands talk directly to PostgreSQL through `scripts.ops`.
- `logs` and `restart` use `journalctl` and `systemctl`, so they are meant for the server where the service is installed.
- `restart` uses `sudo systemctl restart ...`, so the deploy or operator user should have passwordless sudo for the specific Rob services.
- A minimal sudoers entry is usually enough, for example:

```sudoers
Cmnd_Alias ROB_BOT_CTL = /bin/systemctl restart rob-bot-dev.service, /usr/bin/systemctl restart rob-bot-dev.service
Cmnd_Alias ROB_WEBHOOK_CTL = /bin/systemctl restart rob-webhook-dev.service, /usr/bin/systemctl restart rob-webhook-dev.service
deployuser ALL=(root) NOPASSWD: ROB_BOT_CTL, ROB_WEBHOOK_CTL
```

- `queue flush` refuses to run while maintenance mode is still enabled.

- 2026-05-22: Public send card now uses compact Components V2 layout with real `discord.ui.Separator()` and purple accent constants from `rob/ui/theme.py`; rank lines/footer removed.
- 2026-05-22: Added NEW LEADER ALERT card (purple accent, separator-based sections) for leaderboard #1 changes (posting logic TODO/dedupe wired in queue path).
- 2026-05-22: Leaderboard and stats cards now use explicit separator components; stats include Unclaimed Sends section.
- 2026-05-22: `/send details` command + public Rob Send ID flow remains TODO for follow-up implementation; public send cards intentionally omit Rob Send ID.
