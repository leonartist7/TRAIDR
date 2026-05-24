from decimal import Decimal

from execution.liquidity_depth import (
    estimate_liquidity_depth,
    liquidity_penalized_notional,
)


def test_liquidity_depth_estimates_size_based_slippage() -> None:
    estimate = estimate_liquidity_depth(
        order_notional_usd=Decimal("10"),
        liquidity_usd=Decimal("1000"),
    )

    assert estimate.order_to_liquidity_ratio == Decimal("0.01")
    assert estimate.estimated_slippage_bps == Decimal("200.00")
    assert estimate.fill_fraction == Decimal("1")
    assert estimate.penalty_reason_codes == ("LIQUIDITY_THIN",)


def test_liquidity_depth_penalizes_large_orders_and_partial_fills() -> None:
    estimate = estimate_liquidity_depth(
        order_notional_usd=Decimal("300"),
        liquidity_usd=Decimal("1000"),
    )

    assert estimate.fill_fraction == Decimal("0.6666666666666666666666666667")
    assert estimate.estimated_slippage_bps == Decimal("6000.0")
    assert estimate.penalty_reason_codes == (
        "LIQUIDITY_THIN",
        "ORDER_SIZE_LIQUIDITY_IMPACT",
        "PARTIAL_FILL_EXPECTED",
    )
    assert liquidity_penalized_notional(
        requested_notional_usd=Decimal("300"),
        liquidity_usd=Decimal("1000"),
    ) == Decimal("200.0000000000000000000000000")


def test_liquidity_depth_zero_liquidity_has_no_exit_fill() -> None:
    estimate = estimate_liquidity_depth(
        order_notional_usd=Decimal("10"),
        liquidity_usd=Decimal("0"),
    )

    assert estimate.fill_fraction == Decimal("0")
    assert estimate.estimated_slippage_bps == Decimal("10000")
    assert estimate.penalty_reason_codes == (
        "LIQUIDITY_UNAVAILABLE",
        "EXIT_FILL_UNAVAILABLE",
    )
