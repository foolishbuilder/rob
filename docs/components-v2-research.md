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
