from decimal import Decimal

from execution.rug_crash_model import simulate_liquidity_drain, simulate_rug_crash


def test_liquidity_drain_partially_fills_exit() -> None:
    result = simulate_liquidity_drain(
        starting_liquidity_usd=Decimal("100"),
        drain_fraction=Decimal("0.75"),
        requested_exit_notional_usd=Decimal("50"),
    )

    assert result.remaining_liquidity_usd == Decimal("25.00")
    assert result.filled_exit_notional_usd == Decimal("25.00")
    assert result.fill_fraction == Decimal("0.50")
    assert result.reason_codes == ("LIQUIDITY_DRAIN_SIMULATED", "EXIT_PARTIAL_FILL")


def test_liquidity_drain_can_make_exit_unfillable() -> None:
    result = simulate_liquidity_drain(
        starting_liquidity_usd=Decimal("100"),
        drain_fraction=Decimal("1"),
        requested_exit_notional_usd=Decimal("10"),
    )

    assert result.remaining_liquidity_usd == Decimal("0")
    assert result.fill_fraction == Decimal("0")
    assert result.reason_codes == ("LIQUIDITY_DRAIN_SIMULATED", "EXIT_FILL_UNAVAILABLE")


def test_rug_crash_models_price_collapse_and_liquidity_drain() -> None:
    result = simulate_rug_crash(
        pre_crash_price_usd=Decimal("1.00"),
        starting_liquidity_usd=Decimal("100"),
        price_crash_fraction=Decimal("0.95"),
        liquidity_drain_fraction=Decimal("0.99"),
        requested_exit_notional_usd=Decimal("10"),
    )

    assert result.post_crash_price_usd == Decimal("0.0500")
    assert result.remaining_liquidity_usd == Decimal("1.00")
    assert result.exit_fill_fraction == Decimal("0.10")
    assert result.reason_codes == (
        "RUG_CRASH_SIMULATED",
        "PRICE_COLLAPSE_SIMULATED",
        "LIQUIDITY_DRAIN_SIMULATED",
        "EXIT_PARTIAL_FILL",
        "CATASTROPHIC_RUG_CRASH",
    )
