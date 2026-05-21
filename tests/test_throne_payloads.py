from __future__ import annotations

from rob.throne.payloads import is_explicit_test_webhook_payload, is_known_test_sender, parse_throne_send_payload


def test_gift_purchased_price_parses_to_amount_cents():
    parsed = parse_throne_send_payload(creator_id='c', payload={'type':'gift_purchased','data':{'price':1099,'currency':'USD','item_name':'x','item_thumbnail_url':'https://x','gifter_username':'sub'}})
    assert parsed.amount_cents == 1099


def test_contribution_amount_minor_units():
    parsed = parse_throne_send_payload(creator_id='c', payload={'event_type':'contribution_purchased','data':{'amount':1500,'currency':'EUR'}})
    assert parsed.amount_cents == 1500


def test_gift_crowdfunded_allows_missing_gifter_username():
    parsed = parse_throne_send_payload(creator_id='c', payload={'type':'gift_crowdfunded','data':{'price':1099,'currency':'USD'}})
    assert parsed.gifter_username is None
    assert parsed.amount_cents == 1099


def test_explicit_test_payload_is_detected():
    payload = {'type':'webhook.test','data':{'isTest':True}}
    parsed = parse_throne_send_payload(creator_id='c', payload=payload)
    assert is_explicit_test_webhook_payload(payload, parsed) is True


def test_known_test_sender_detection():
    assert is_known_test_sender('marie_123', test_gifter_usernames={'marie_123'}) is True


def test_real_sender_not_known_test_sender():
    assert is_known_test_sender('real_sender', test_gifter_usernames={'marie_123'}) is False
