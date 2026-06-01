from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import discord

_REQUIRED_V2 = ("LayoutView", "Container", "Section", "TextDisplay", "Separator", "MediaGallery", "Thumbnail", "Button")
CardVariant = Literal[
    "default",
    "success",
    "error",
    "warning",
    "setup",
    "leaderboard",
    "send",
    "counting",
    "status",
    "celebration",
    "dashboard",
    "workflow",
    "danger",
]


@dataclass(frozen=True)
class CardSection:
    title: str
    text: str
    inline: bool = False


@dataclass(frozen=True)
class CardAction:
    label: str
    style: discord.ButtonStyle = discord.ButtonStyle.secondary
    custom_id: str | None = None
    url: str | None = None
    row: int | None = None


@dataclass(frozen=True)
class RobCard:
    title: str
    body: str
    sections: list[CardSection] = field(default_factory=list)
    footer: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    actions: list[CardAction] = field(default_factory=list)
    color: discord.Colour | None = None
    variant: CardVariant = "default"
    eyebrow: str | None = None
    callout: str | None = None
    code_block: str | None = None


@dataclass(frozen=True)
class RenderedMessage:
    content: str | None = None
    view: discord.ui.View | discord.ui.LayoutView | None = None
    embeds: list[discord.Embed] = field(default_factory=list)
    mode: Literal["components_v2", "embed"] = "components_v2"

    def send_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.content is not None:
            payload["content"] = self.content
        if self.embeds:
            payload["embeds"] = list(self.embeds)
        if self.view is not None:
            payload["view"] = self.view
        return payload

    def edit_kwargs(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "embeds": list(self.embeds),
            "attachments": [],
            "view": self.view,
        }


def supports_components_v2() -> bool:
    return all(hasattr(discord.ui, name) for name in _REQUIRED_V2)


def require_components_v2() -> None:
    if supports_components_v2():
        return
    missing = [name for name in _REQUIRED_V2 if not hasattr(discord.ui, name)]
    raise RuntimeError(f"Discord Components V2 is required for Rob card rendering. Missing: {', '.join(missing)}")


def build_action_row(*buttons: discord.ui.Button) -> discord.ui.ActionRow:
    if not hasattr(discord.ui, "ActionRow"):
        raise RuntimeError("discord.ui.ActionRow is required to place buttons in Components V2 layouts.")
    return discord.ui.ActionRow(*buttons)


def add_card_actions(view: discord.ui.LayoutView, *buttons: discord.ui.Button) -> None:
    if not buttons:
        return
    view.add_item(build_action_row(*buttons))


# ---------------------------------------------------------------------------
# Variant-driven presentation helpers
# ---------------------------------------------------------------------------

_VARIANT_TITLE_PREFIX: dict[str, str] = {
    "celebration": "🎉",
    "send": "💸",
    "dashboard": "📊",
    "leaderboard": "🏆",
    "workflow": "📋",
    "setup": "🔧",
    "warning": "⚠️",
    "danger": "🚨",
    "error": "❌",
    "success": "✅",
}

_VARIANT_HEADING_LEVEL: dict[str, str] = {
    "celebration": "##",
    "send": "##",
    "dashboard": "##",
    "leaderboard": "##",
    "default": "##",
    "success": "##",
    "error": "##",
    "warning": "###",
    "danger": "###",
    "workflow": "###",
    "setup": "###",
    "counting": "##",
    "status": "##",
}


def _format_title(title: str, variant: CardVariant) -> str:
    heading = _VARIANT_HEADING_LEVEL.get(variant, "##")
    prefix = _VARIANT_TITLE_PREFIX.get(variant, "")
    if prefix:
        return f"{heading} {prefix} {title}"
    return f"{heading} {title}"


# ---------------------------------------------------------------------------
# Reusable composition helpers
# ---------------------------------------------------------------------------


def make_metadata_row(label: str, value: str) -> str:
    """Format a quiet metadata line: `-# Label: Value`."""
    return f"-# {label}: {value}"


def make_metric_display(label: str, value: str) -> str:
    """Format a metric for dashboard/stats cards: label above bold value."""
    return f"-# {label}:\n**{value}**"


def make_inline_metrics(metrics: list[tuple[str, str]], *, separator: str = " · ") -> str:
    """Format multiple metrics on one compact line."""
    parts = [f"**{v}** {k}" for k, v in metrics]
    return separator.join(parts)


def make_cta_text(text: str) -> str:
    """Format a call-to-action hint."""
    return f"-# {text}"


def build_thumbnail_section(
    body_text: str,
    thumbnail_url: str,
) -> discord.ui.Section:
    """Create a Section with text and a Thumbnail accessory."""
    return discord.ui.Section(
        discord.ui.TextDisplay(body_text),
        accessory=discord.ui.Thumbnail(media=thumbnail_url),
    )


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------


def render_card(card: RobCard, *, view: discord.ui.LayoutView | None = None) -> RenderedMessage:
    require_components_v2()
    if view is not None and len(view.children) > 0:
        raise RuntimeError("render_card(view=...) expects an empty LayoutView.")
    layout = view or discord.ui.LayoutView(timeout=1800)
    items: list[Any] = []

    # Eyebrow
    if card.eyebrow:
        items.append(discord.ui.TextDisplay(f"-# {card.eyebrow}"))

    # Title — variant drives heading level and optional emoji prefix
    items.append(discord.ui.TextDisplay(_format_title(card.title, card.variant)))

    items.append(discord.ui.Separator())

    # Body — optionally as a Section with thumbnail accessory
    if card.thumbnail_url:
        items.append(
            discord.ui.Section(
                discord.ui.TextDisplay(card.body),
                accessory=discord.ui.Thumbnail(media=card.thumbnail_url),
            )
        )
    else:
        items.append(discord.ui.TextDisplay(card.body))

    # Callout
    if card.callout:
        items.append(discord.ui.Separator())
        items.append(discord.ui.TextDisplay(card.callout))

    # Code block
    if card.code_block:
        items.append(discord.ui.TextDisplay(f"```\n{card.code_block}\n```"))

    # Sections — inline sections rendered as compact metric rows
    if card.sections:
        inline_sections = [s for s in card.sections if s.inline]
        block_sections = [s for s in card.sections if not s.inline]

        if inline_sections:
            items.append(discord.ui.Separator())
            metrics_text = " · ".join(f"**{s.title}:** {s.text}" for s in inline_sections)
            items.append(discord.ui.TextDisplay(metrics_text))

        if block_sections:
            items.append(discord.ui.Separator())
            for section in block_sections:
                items.append(discord.ui.TextDisplay(f"**{section.title}**\n{section.text}"))

    # Image gallery
    if card.image_url:
        items.append(discord.ui.Separator())
        items.append(discord.ui.MediaGallery(discord.MediaGalleryItem(media=card.image_url)))

    # Footer
    if card.footer:
        items.append(discord.ui.Separator())
        items.append(discord.ui.TextDisplay(f"-# {card.footer}"))

    layout.add_item(discord.ui.Container(*items, accent_color=card.color))

    # Actions — render CardAction list automatically as an ActionRow
    if card.actions:
        buttons: list[discord.ui.Button] = []
        for action in card.actions:
            btn = discord.ui.Button(label=action.label, style=action.style)
            if action.custom_id:
                btn.custom_id = action.custom_id
            if action.url:
                btn.url = action.url
            buttons.append(btn)
        add_card_actions(layout, *buttons)

    return RenderedMessage(view=layout)
