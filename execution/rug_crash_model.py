"""Simulation-only liquidity drain and catastrophic rug crash scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LiquidityDrainResult:
    """Exit result after simulated liquidity is drained."""

    starting_liquidity_usd: Decimal
    remaining_liquidity_usd: Decimal
    requested_exit_notional_usd: Decimal
    filled_exit_notional_usd: Decimal
    fill_fraction: Decimal
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class RugCrashResult:
    """Catastrophic paper mark-down scenario."""

    pre_crash_price_usd: Decimal
    post_crash_price_usd: Decimal
    remaining_liquidity_usd: Decimal
    crash_loss_fraction: Decimal
    exit_fill_fraction: Decimal
    reason_codes: tuple[str, ...]


def simulate_liquidity_drain(
    *,
    starting_liquidity_usd: Decimal,
    drain_fraction: Decimal,
    requested_exit_notional_usd: Decimal,
) -> LiquidityDrainResult:
    """Simulate exit capacity after liquidity disappears from a paper market."""

    if starting_liquidity_usd < Decimal("0"):
        raise ValueError("starting liquidity cannot be negative")
    if requested_exit_notional_usd <= Decimal("0"):
        raise ValueError("requested exit notional must be positive")
    if drain_fraction < Decimal("0") or drain_fraction > Decimal("1"):
        raise ValueError("drain fraction must be in [0, 1]")

    remaining = starting_liquidity_usd * (Decimal("1") - drain_fraction)
    filled = min(requested_exit_notional_usd, remaining)
    fill_fraction = filled / requested_exit_notional_usd
    reasons: list[str] = ["LIQUIDITY_DRAIN_SIMULATED"]
    if remaining == Decimal("0"):
        reasons.append("EXIT_FILL_UNAVAILABLE")
    elif fill_fraction < Decimal("1"):
        reasons.append("EXIT_PARTIAL_FILL")

    return LiquidityDrainResult(
        starting_liquidity_usd=starting_liquidity_usd,
        remaining_liquidity_usd=remaining,
        requested_exit_notional_usd=requested_exit_notional_usd,
        filled_exit_notional_usd=filled,
        fill_fraction=fill_fraction,
        reason_codes=tuple(reasons),
    )


def simulate_rug_crash(
    *,
    pre_crash_price_usd: Decimal,
    starting_liquidity_usd: Decimal,
    price_crash_fraction: Decimal = Decimal("0.95"),
    liquidity_drain_fraction: Decimal = Decimal("0.99"),
    requested_exit_notional_usd: Decimal = Decimal("10"),
) -> RugCrashResult:
    """Simulate a catastrophic paper crash with price collapse and liquidity drain."""

    if pre_crash_price_usd <= Decimal("0"):
        raise ValueError("pre-crash price must be positive")
    if price_crash_fraction < Decimal("0") or price_crash_fraction > Decimal("1"):
        raise ValueError("price crash fraction must be in [0, 1]")

    drain = simulate_liquidity_drain(
        starting_liquidity_usd=starting_liquidity_usd,
        drain_fraction=liquidity_drain_fraction,
        requested_exit_notional_usd=requested_exit_notional_usd,
    )
    post_price = pre_crash_price_usd * (Decimal("1") - price_crash_fraction)
    reasons = [
        "RUG_CRASH_SIMULATED",
        "PRICE_COLLAPSE_SIMULATED",
        *drain.reason_codes,
    ]
    if price_crash_fraction >= Decimal("0.90"):
        reasons.append("CATASTROPHIC_RUG_CRASH")

    return RugCrashResult(
        pre_crash_price_usd=pre_crash_price_usd,
        post_crash_price_usd=post_price,
        remaining_liquidity_usd=drain.remaining_liquidity_usd,
        crash_loss_fraction=price_crash_fraction,
        exit_fill_fraction=drain.fill_fraction,
        reason_codes=tuple(dict.fromkeys(reasons)),
    )
