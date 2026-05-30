from __future__ import annotations

from rob.achievements.definitions import ACHIEVEMENTS, ACHIEVEMENTS_BY_KEY
from rob.achievements.embeds import achievement_unlocked_card, achievements_overview_cards


def _card_text(card) -> str:
    if card.embeds:
        embed = card.embeds[0]
        parts = [embed.title or "", embed.description or ""]
        parts.extend(field.name for field in embed.fields)
        parts.extend(field.value for field in embed.fields)
        parts.append(embed.footer.text if embed.footer else "")
        return "\n".join(part for part in parts if part)

    view = card.view
    assert view is not None
    return "\n".join(
        str(getattr(item, "content", ""))
        for container in view.children
        for item in getattr(container, "children", [])
    )


def test_achievements_catalogue_uses_compact_embed_field_layout():
    cards = achievements_overview_cards(
        display_name="Pat",
        unlocked_keys={"count_10"},
        for_self=True,
    )
    embed = cards[0].embeds[0]
    text = _card_text(cards[0])
    assert embed.title == "Rob Achievements"
    assert "Achievements unlocked (total): 1/" in (embed.description or "")
    assert any(field.name == "Double Digits" for field in embed.fields)
    assert "You counted to 10. Humanity may yet survive." in text


def test_locked_catalogue_entries_render_even_when_user_has_none_unlocked():
    cards = achievements_overview_cards(
        display_name="Pat",
        unlocked_keys=set(),
        for_self=True,
    )
    text = "\n".join(_card_text(card) for card in cards)
    assert "Double Digits" in text
    assert "You counted to 10. Humanity may yet survive." in text


def test_catalogue_pages_cap_entries_per_page_to_fifteen():
    unlocked_keys = {achievement.key for achievement in ACHIEVEMENTS}
    cards = achievements_overview_cards(
        display_name="Pat",
        unlocked_keys=unlocked_keys,
        for_self=True,
    )
    assert cards
    for card in cards:
        assert len(card.embeds[0].fields) <= 15


def test_unlock_card_uses_plain_title_and_unlocked_by_line():
    achievement = ACHIEVEMENTS_BY_KEY["count_4321"]
    card = achievement_unlocked_card(
        achievement,
        unlocked_by_display_name="Adore's Pickle Pat",
    )
    text = _card_text(card)
    assert "Achievement Unlocked" not in text
    assert f"### {achievement.title}" in text
    assert achievement.description in text
    assert "Unlocked by Adore's Pickle Pat" in text


def test_unlock_card_hides_debug_metadata_by_default():
    achievement = ACHIEVEMENTS_BY_KEY["sub_100_sent"]
    card = achievement_unlocked_card(achievement, unlocked_by_display_name="Pat")
    text = _card_text(card)
    assert "Key:" not in text
    assert "Category:" not in text
    assert "Rarity:" not in text


def test_unlock_card_can_show_debug_metadata_when_explicitly_enabled():
    achievement = ACHIEVEMENTS_BY_KEY["sub_100_sent"]
    card = achievement_unlocked_card(
        achievement,
        unlocked_by_display_name="Pat",
        include_meta_line=True,
    )
    text = _card_text(card)
    assert "Key:" in text
