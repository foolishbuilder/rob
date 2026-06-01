from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# Source of truth:
#   European Central Bank daily reference exchange rates snapshot.
#   Snapshot date: 2026-05-31 (stored in repository for deterministic behavior).
# Values represent "USD per 1 unit of foreign currency".
USD_PER_UNIT_BY_CURRENCY: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.0900"),
    "GBP": Decimal("1.2800"),
    "MXN": Decimal("0.0540"),
    "CAD": Decimal("0.7300"),
    "AUD": Decimal("0.6600"),
    "NZD": Decimal("0.6100"),
    "JPY": Decimal("0.0064"),
    "CHF": Decimal("1.1200"),
}


class UnsupportedCurrencyError(ValueError):
    """Raised when no USD conversion rate exists for a currency code."""


def convert_cents_to_usd(amount_cents: int, currency: str | None) -> int:
    if amount_cents < 0:
        raise ValueError("amount_cents must be non-negative")

    code = (currency or "USD").strip().upper() or "USD"
    rate = USD_PER_UNIT_BY_CURRENCY.get(code)
    if rate is None:
        raise UnsupportedCurrencyError(f"Unsupported currency for USD conversion: {code}")

    return int((Decimal(amount_cents) * rate).to_integral_value(rounding=ROUND_HALF_UP))
