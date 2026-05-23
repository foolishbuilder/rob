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
- Explicit test/setup webhook payloads are detected before send insertion.
- Explicit test events update creator setup verification timestamps (`setup_verified_at`, `last_test_webhook_at`, `last_successful_event_at`) and return `{"ok": true, "setup_verified": true}`.
- Explicit test events do not insert `sends` rows and do not enter the Discord send tracker queue.
- Known test senders can still be stored as real queue items for visible card flow, but are marked `is_test_send=true` and excluded from leaderboards unless test parsing is enabled or the configured owner/test recipient override applies.
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


## 2026-05 update
- Added explicit v2 priority calls: inactivity P1, DM audit P2/P3, Carl warn relay P2, local admin endpoints/shell helpers P1/P2.
- Event runtime remains intentionally not ported unless explicitly requested.

## Phase 1 implementation scope (current branch)
- Focused on high-impact day-to-day runtime parity only: Components V2 card path, registration setup flow/card copy, send card style parity, and leaderboard main+stats runtime wiring.
- Explicitly deferred to follow-up PRs: inactivity removal, DM audit forwarding, Carl-bot warn relay, rule helper, and event-window runtime/reporting.
- Kept architecture guardrails intact: split bot/webhook services, PostgreSQL runtime, no SQLite reintroduction, no legacy single-process bot merge.

- 2026-05-23: Public send card now uses compact Components V2 layout with real `discord.ui.Separator()`, thumbnails, friendly currency names, and purple accent constants from `rob/ui/theme.py`; public send IDs stay out of the public announcement card.
- 2026-05-23: NEW LEADER ALERT posting is now wired live with bot-state dedupe and test-send exclusion.
- 2026-05-23: Leaderboard and stats cards now use explicit separator components, include registered zero-send Dommes, and show dynamic maintenance/live status on the main board.
- 2026-05-23: Public send IDs are stored in PostgreSQL and can be backfilled via `robctl sends backfill-public-ids`; public send cards still omit IDs.
