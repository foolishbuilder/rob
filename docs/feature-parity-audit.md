# Rob Feature Parity Audit

| Feature | Old bot | New bot before patch | New bot after patch | Status |
|---|---|---|---|---|
| counting | full legacy restore workflow | basic react-only count checks | still partial; major restore flow remains TODO | Partial |
| `/add` | manual send logging | available | available with current architecture | Complete |
| `/sendrequest` | DM approve/ignore buttons | DM with suggested `/add` only | still DM-only suggestion (button parity pending) | Partial |
| send request approve/ignore buttons | present | missing | missing | Missing |
| Domme registration | setup DM flow and webhook guidance | simple registration response with URL | new DM setup flow and hidden URL in command response | Partial |
| Sub registration | available | available | available | Complete |
| Throne webhook tracking | tracked webhook events | tracked webhook events | tracked webhook events | Complete |
| leaderboards | top leaderboard formatting | generic summary format | top-10 Dom/me formatting and cleaner totals | Partial |
| backend `robctl` / old `throne` commands | broad command set | reduced set | reduced set (expansion pending) | Missing |
| blacklist commands | command family available | backend support | backend support | Partial |
| rule command | legacy text command | not present | not present | Missing |
| DM audit | partial admin auditing in legacy | not ported | not ported | Missing |
| Carl-bot warn handling | integration existed | not present | not present | Missing |
| manual send methods | broad method list | reduced methods | reduced methods (parity pending) | Partial |
| UI/cards | legacy style | mixed embeds | true LayoutView/Container/TextDisplay rendering with no embed fallback | Complete |

## Notes

This patch intentionally preserves split webhook/bot services and PostgreSQL-only runtime architecture, and does not reintroduce event-bot/event-window behavior.


## Throne test webhook handling
- Test/setup webhook payloads are detected before send insertion.
- Test events update creator setup verification timestamps (`setup_verified_at`, `last_test_webhook_at`, `last_successful_event_at`) and return `{"ok": true, "setup_verified": true}`.
- Test events do not insert `sends` rows and do not enter the Discord send tracker queue.
- Runtime now uses true LayoutView-based Components V2 rendering when supported, with automatic no embed fallback if required V2 classes are unavailable.

## Old Rob wording / copy reference

- Sources checked:
  - `notpatdev/rob-the-bot` (not accessible from this workspace)
  - `legacy/single-process-bot/` (fallback used)
- Copy restored:
  - registration
  - Throne setup
  - errors/snag-paperwork tone
- Copy intentionally changed:
  - copy was centralized into `rob/ui/copy.py` constants/helpers so cogs stop hardcoding long user-facing blocks.
