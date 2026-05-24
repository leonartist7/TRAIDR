"""Simulation-only liquidity depth and size-based slippage estimates."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

THIN_LIQUIDITY_THRESHOLD_USD = Decimal("10000")
SEVERE_IMPACT_RATIO = Decimal("0.20")
_BPS = Decimal("10000")


@dataclass(frozen=True)
class LiquidityDepthEstimate:
    """Deterministic liquidity impact estimate for paper simulation."""

    liquidity_usd: Decimal
    order_notional_usd: Decimal
    order_to_liquidity_ratio: Decimal
    estimated_slippage_bps: Decimal
    fill_fraction: Decimal
    penalty_reason_codes: tuple[str, ...]

    @property
    def thin_liquidity(self) -> bool:
        return "LIQUIDITY_THIN" in self.penalty_reason_codes


def estimate_liquidity_depth(
    *,
    order_notional_usd: Decimal,
    liquidity_usd: Decimal,
) -> LiquidityDepthEstimate:
    """Estimate paper slippage and fill fraction from order size over liquidity."""

    if order_notional_usd <= Decimal("0"):
        raise ValueError("order notional must be positive")
    if liquidity_usd <= Decimal("0"):
        return LiquidityDepthEstimate(
            liquidity_usd=liquidity_usd,
            order_notional_usd=order_notional_usd,
            order_to_liquidity_ratio=Decimal("1"),
            estimated_slippage_bps=_BPS,
            fill_fraction=Decimal("0"),
            penalty_reason_codes=("LIQUIDITY_UNAVAILABLE", "EXIT_FILL_UNAVAILABLE"),
        )

    ratio = order_notional_usd / liquidity_usd
    slippage_bps = min(_BPS, _BPS * ratio * Decimal("2"))
    fill_fraction = Decimal("1") if ratio <= SEVERE_IMPACT_RATIO else max(
        Decimal("0.05"),
        SEVERE_IMPACT_RATIO / ratio,
    )
    reasons: list[str] = []
    if liquidity_usd < THIN_LIQUIDITY_THRESHOLD_USD:
        reasons.append("LIQUIDITY_THIN")
    if ratio > Decimal("0.05"):
        reasons.append("ORDER_SIZE_LIQUIDITY_IMPACT")
    if fill_fraction < Decimal("1"):
        reasons.append("PARTIAL_FILL_EXPECTED")

    return LiquidityDepthEstimate(
        liquidity_usd=liquidity_usd,
        order_notional_usd=order_notional_usd,
        order_to_liquidity_ratio=ratio,
        estimated_slippage_bps=slippage_bps,
        fill_fraction=fill_fraction,
        penalty_reason_codes=tuple(reasons),
    )


def liquidity_penalized_notional(
    *,
    requested_notional_usd: Decimal,
    liquidity_usd: Decimal,
) -> Decimal:
    """Return the simulated notional expected to fill after liquidity depth limits."""

    estimate = estimate_liquidity_depth(
        order_notional_usd=requested_notional_usd,
        liquidity_usd=liquidity_usd,
    )
    return requested_notional_usd * estimate.fill_fraction
