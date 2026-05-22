"""Twenty percent take-profit checks for simulated positions."""

from __future__ import annotations

from decimal import Decimal

TAKE_PROFIT_RATE = Decimal("0.20")


def take_profit_price(entry_price_usd: Decimal) -> Decimal:
    """Return the 20% simulated take-profit target."""

    if entry_price_usd <= Decimal("0"):
        raise ValueError("entry price must be positive")
    return entry_price_usd * (Decimal("1") + TAKE_PROFIT_RATE)


def should_take_profit(entry_price_usd: Decimal, current_price_usd: Decimal) -> bool:
    """Report whether a simulated position reached its 20% target."""

    if current_price_usd <= Decimal("0"):
        raise ValueError("current price must be positive")
    return current_price_usd >= take_profit_price(entry_price_usd)

