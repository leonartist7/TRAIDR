"""Deterministic paper slippage and fill simulation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from risk.models import IntentAction

DEFAULT_SLIPPAGE_RATE = Decimal("0.005")
_MONEY_QUANTUM = Decimal("0.00000001")
_QUANTITY_QUANTUM = Decimal("0.000000000001")


@dataclass(frozen=True)
class FillQuote:
    """Slippage-adjusted values for a simulated fill."""

    price_usd: Decimal
    notional_usd: Decimal
    quantity: Decimal
    fill_fraction: Decimal


def quote_fill(
    *,
    side: IntentAction,
    reference_price_usd: Decimal,
    approved_notional_usd: Decimal,
    fill_fraction: Decimal,
    slippage_rate: Decimal = DEFAULT_SLIPPAGE_RATE,
) -> FillQuote:
    """Apply adverse slippage and partial fill fraction deterministically."""

    if side not in (IntentAction.BUY, IntentAction.SELL):
        raise ValueError("paper fill quote requires a buy or sell side")
    if reference_price_usd <= Decimal("0"):
        raise ValueError("reference price must be positive")
    if approved_notional_usd <= Decimal("0"):
        raise ValueError("approved notional must be positive")
    if fill_fraction <= Decimal("0") or fill_fraction > Decimal("1"):
        raise ValueError("fill fraction must be in (0, 1]")
    if slippage_rate < Decimal("0") or slippage_rate >= Decimal("1"):
        raise ValueError("slippage rate must be in [0, 1)")

    direction = Decimal("1") + slippage_rate if side is IntentAction.BUY else Decimal("1") - slippage_rate
    price_usd = (reference_price_usd * direction).quantize(_QUANTITY_QUANTUM)
    notional_usd = (approved_notional_usd * fill_fraction).quantize(
        _MONEY_QUANTUM,
        rounding=ROUND_DOWN,
    )
    quantity = (notional_usd / price_usd).quantize(
        _QUANTITY_QUANTUM,
        rounding=ROUND_DOWN,
    )
    return FillQuote(price_usd, notional_usd, quantity, fill_fraction)

