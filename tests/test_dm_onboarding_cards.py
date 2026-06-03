"""Smoke tests for the DM-onboarding Components V2 cards."""

from __future__ import annotations

import discord

from rob.ui.cards.dm_onboarding import (
    LEADERBOARD_HIDE_VALUE,
    LEADERBOARD_SHOW_VALUE,
    NOTIFY_OFF_VALUE,
    NOTIFY_ON_VALUE,
    PreferencesView,
    build_intro_modal,
    identity_confirm_card,
    intro_card,
    migration_prompt_card,
    preferences_card,
    success_card,
    webhook_setup_card,
    webhook_waiting_card,
)


def _has_button_with_id(view: discord.ui.LayoutView, custom_id: str) -> bool:
    for item in view.walk_children():
        if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
            return True
    return False


def test_intro_card_has_modal_open_button():
    rendered = intro_card()
    assert _has_button_with_id(rendered.view, "rob:dm_onboarding:intro:open_modal")


def test_intro_modal_has_throne_field():
    modal = build_intro_modal()
    assert modal.custom_id == "rob:dm_onboarding:intro:modal"
    # The TextInput field is a class attribute on the Modal subclass.
    children = list(modal.children)
    assert any(getattr(c, "custom_id", None) == "rob:dm_onboarding:intro:modal:throne_input" for c in children)


def test_identity_confirm_card_has_yes_and_no_buttons():
    rendered = identity_confirm_card(throne_handle="cool", throne_display_name="Cool")
    assert _has_button_with_id(rendered.view, "rob:dm_onboarding:identity:yes")
    assert _has_button_with_id(rendered.view, "rob:dm_onboarding:identity:no")


def test_webhook_setup_card_includes_webhook_url():
    rendered = webhook_setup_card(webhook_url="https://example.com/webhook/abc")
    # The URL should appear somewhere in the rendered layout view (via TextDisplay).
    found = False
    for item in rendered.view.walk_children():
        if isinstance(item, discord.ui.TextDisplay) and "https://example.com/webhook/abc" in item.content:
            found = True
            break
    assert found


def test_webhook_waiting_card_renders():
    rendered = webhook_waiting_card()
    assert rendered.view is not None


def test_preferences_view_defaults_and_save_button():
    view = PreferencesView(default_notifications_enabled=True, default_leaderboard_visible=False)
    # Defaults are reflected in select options.
    notify_defaults = [o for o in view.notifications_select.options if o.default]
    assert notify_defaults and notify_defaults[0].value == NOTIFY_ON_VALUE
    lb_defaults = [o for o in view.leaderboard_select.options if o.default]
    assert lb_defaults and lb_defaults[0].value == LEADERBOARD_HIDE_VALUE

    # Save button is exposed via attribute and present in the view tree.
    assert view.save_button.custom_id == "rob:dm_onboarding:prefs:save"
    assert _has_button_with_id(view, "rob:dm_onboarding:prefs:save")


def test_preferences_view_chosen_values_default_to_true():
    view = PreferencesView()
    # No values set yet, properties fall back to True.
    assert view.chosen_notifications_enabled is True
    assert view.chosen_leaderboard_visible is True


def test_preferences_view_chosen_values_reflect_selection():
    view = PreferencesView()
    view.notifications_select._values = [NOTIFY_OFF_VALUE]  # type: ignore[attr-defined]
    view.leaderboard_select._values = [LEADERBOARD_SHOW_VALUE]  # type: ignore[attr-defined]
    assert view.chosen_notifications_enabled is False
    assert view.chosen_leaderboard_visible is True


def test_preferences_card_returns_view():
    rendered = preferences_card()
    assert isinstance(rendered.view, PreferencesView)


def test_success_card_messages_reflect_choices():
    rendered_on = success_card(notifications_enabled=True, leaderboard_visible=True)
    rendered_off = success_card(notifications_enabled=False, leaderboard_visible=False)
    on_text = " ".join(
        i.content for i in rendered_on.view.walk_children() if isinstance(i, discord.ui.TextDisplay)
    )
    off_text = " ".join(
        i.content for i in rendered_off.view.walk_children() if isinstance(i, discord.ui.TextDisplay)
    )
    assert "DM" in on_text
    assert "off" in off_text.lower()


def test_migration_card_has_set_and_defer_buttons():
    rendered = migration_prompt_card()
    assert _has_button_with_id(rendered.view, "rob:dm_migration:open_prefs")
    assert _has_button_with_id(rendered.view, "rob:dm_migration:defer_7d")
