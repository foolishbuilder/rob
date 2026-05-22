# Components V2 research

## Button placement research

### Discord docs findings
- Discord Components reference says buttons must be inside an Action Row or in a Section `accessory`.
- Container is a layout wrapper and can hold layout/content components; interactive buttons still must follow button placement rules.

### discord.py findings
- Runtime verified on discord.py 2.7.1 (`discord.__version__ == 2.7.1`).
- `discord.ui.Container`, `ActionRow`, `Section`, `Button`, `TextDisplay`, and `LayoutView` are present.
- Valid, supported pattern for two buttons is `Container` + `ActionRow(button1, button2)` in the same `LayoutView`.
- `Section(..., accessory=Button(...))` is valid when you need one accessory button.

### notpatdev/rob-the-bot findings
- `notpatdev/rob-the-bot` was not available in this workspace, so it could not be inspected directly.
- Used `legacy/single-process-bot/` as the local fallback source for tone/copy references.
- Legacy bot copy is reusable, but its architecture is not the same as the current clean Components V2 renderer.

### Final Rob implementation decision
- Rob keeps the card container first, then adds actions via a helper that always wraps buttons in an `ActionRow`.
- Rob does not place raw top-level `Button` objects in `LayoutView`.
- This keeps payloads valid and avoids the prior `Invalid Form Body` error.


## 2026-05 legacy parity update
- Adopted container-first card templates with action rows (no raw top-level buttons).
- Documented fallback policy and old-Rob copy parity targets.

- 2026-05-22: Public send card now uses compact Components V2 layout with real `discord.ui.Separator()` and purple accent constants from `rob/ui/theme.py`; rank lines/footer removed.
- 2026-05-22: Added NEW LEADER ALERT card (purple accent, separator-based sections) for leaderboard #1 changes (posting logic TODO/dedupe wired in queue path).
- 2026-05-22: Leaderboard and stats cards now use explicit separator components; stats include Unclaimed Sends section.
- 2026-05-22: `/send details` command + public Rob Send ID flow remains TODO for follow-up implementation; public send cards intentionally omit Rob Send ID.
