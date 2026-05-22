"""Five percent trailing-stop tracking for simulated positions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

TRAILING_STOP_RATE = Decimal("0.05")


@dataclass(frozen=True)
class TrailingStopState:
    """Immutable trailing-stop state."""

    high_watermark_usd: Decimal
    stop_price_usd: Decimal
    triggered: bool = False


def start_trailing_stop(entry_price_usd: Decimal) -> TrailingStopState:
    """Start a 5% trailing stop from a simulated entry price."""

    _require_positive_price(entry_price_usd)
    return _state_for_high(entry_price_usd, triggered=False)


def update_trailing_stop(
    state: TrailingStopState,
    current_price_usd: Decimal,
) -> TrailingStopState:
    """Move the stop upward with price highs and trigger on a 5% drawdown."""

    _require_positive_price(current_price_usd)
    high = max(state.high_watermark_usd, current_price_usd)
    next_state = _state_for_high(high, triggered=state.triggered)
    return TrailingStopState(
        high_watermark_usd=next_state.high_watermark_usd,
        stop_price_usd=next_state.stop_price_usd,
        triggered=state.triggered or current_price_usd <= next_state.stop_price_usd,
    )


def _state_for_high(high_watermark_usd: Decimal, *, triggered: bool) -> TrailingStopState:
    return TrailingStopState(
        high_watermark_usd=high_watermark_usd,
        stop_price_usd=high_watermark_usd * (Decimal("1") - TRAILING_STOP_RATE),
        triggered=triggered,
    )


def _require_positive_price(price_usd: Decimal) -> None:
    if price_usd <= Decimal("0"):
        raise ValueError("trailing stop prices must be positive")

