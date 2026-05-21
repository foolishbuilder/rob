from __future__ import annotations

from rob.ui.components import make_card, render
from rob.ui.copy import ERROR_FOOTER
from rob.ui.theme import COLOR_DANGER


def error_card(message: str, detail: str | None = None):
    description = message if detail is None else f"{message}\n\n{detail}"
    return render(make_card(title="Rob | Error", body=description, color=COLOR_DANGER, footer=ERROR_FOOTER, variant="error", callout="What to try next: check inputs or try again."))
