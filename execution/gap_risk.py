"""Simulation-only stop-loss gap risk modeling."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class GapRiskResult:
    """Stop execution result when price gaps through a simulated stop."""

    stop_price_usd: Decimal
    next_trade_price_usd: Decimal
    filled_price_usd: Decimal
    gap_loss_fraction: Decimal
    triggered: bool
    reason_codes: tuple[str, ...]


def simulate_stop_loss_gap(
    *,
    entry_price_usd: Decimal,
    stop_price_usd: Decimal,
    next_trade_price_usd: Decimal,
) -> GapRiskResult:
    """Model a stop that can fill below the stop when the next trade gaps down."""

    if entry_price_usd <= Decimal("0") or stop_price_usd <= Decimal("0") or next_trade_price_usd <= Decimal("0"):
        raise ValueError("gap risk prices must be positive")
    if stop_price_usd >= entry_price_usd:
        raise ValueError("stop price must be below entry for long-position simulation")

    triggered = next_trade_price_usd <= stop_price_usd
    filled_price = next_trade_price_usd if triggered else stop_price_usd
    gap_loss = Decimal("0")
    reasons: list[str] = []
    if triggered:
        gap_loss = (stop_price_usd - filled_price) / stop_price_usd
        reasons.append("STOP_LOSS_GAP_TRIGGERED")
        if gap_loss > Decimal("0"):
            reasons.append("STOP_FILLED_BELOW_TRIGGER")
    else:
        reasons.append("STOP_NOT_TRIGGERED")

    return GapRiskResult(
        stop_price_usd=stop_price_usd,
        next_trade_price_usd=next_trade_price_usd,
        filled_price_usd=filled_price,
        gap_loss_fraction=gap_loss,
        triggered=triggered,
        reason_codes=tuple(reasons),
    )
