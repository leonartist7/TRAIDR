from decimal import Decimal

from execution.gap_risk import simulate_stop_loss_gap


def test_stop_loss_gap_fills_below_trigger_when_market_gaps_down() -> None:
    result = simulate_stop_loss_gap(
        entry_price_usd=Decimal("1.00"),
        stop_price_usd=Decimal("0.90"),
        next_trade_price_usd=Decimal("0.50"),
    )

    assert result.triggered is True
    assert result.filled_price_usd == Decimal("0.50")
    assert result.gap_loss_fraction == Decimal("0.4444444444444444444444444444")
    assert result.reason_codes == (
        "STOP_LOSS_GAP_TRIGGERED",
        "STOP_FILLED_BELOW_TRIGGER",
    )


def test_stop_loss_gap_does_not_trigger_above_stop() -> None:
    result = simulate_stop_loss_gap(
        entry_price_usd=Decimal("1.00"),
        stop_price_usd=Decimal("0.90"),
        next_trade_price_usd=Decimal("0.95"),
    )

    assert result.triggered is False
    assert result.filled_price_usd == Decimal("0.90")
    assert result.gap_loss_fraction == Decimal("0")
    assert result.reason_codes == ("STOP_NOT_TRIGGERED",)
