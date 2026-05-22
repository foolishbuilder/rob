from __future__ import annotations

CURRENCY_NAMES = {
    "USD": "United States Dollar",
    "EUR": "Euro",
    "GBP": "British Pound",
    "AUD": "Australian Dollar",
    "CAD": "Canadian Dollar",
    "NZD": "New Zealand Dollar",
}

def dollars_to_cents(amount: float) -> int:
    return int(round(amount * 100))

def format_money_from_cents(amount_cents: int, currency: str = "USD") -> str:
    normalized_currency = (currency or "USD").upper()
    symbol = "$" if normalized_currency == "USD" else normalized_currency + " "
    return f"{symbol}{amount_cents / 100:.2f}"

def format_money_with_currency_name(amount_cents: int, currency: str = "USD") -> str:
    money = format_money_from_cents(amount_cents, currency)
    normalized_currency = (currency or "USD").upper()
    return f"{money} ({CURRENCY_NAMES.get(normalized_currency, normalized_currency)})"
