from decimal import Decimal

from execution.trailing_stop import start_trailing_stop, update_trailing_stop


def test_trailing_stop_moves_up_and_triggers_at_five_percent_drawdown() -> None:
    start = start_trailing_stop(Decimal("10"))
    moved = update_trailing_stop(start, Decimal("12"))
    triggered = update_trailing_stop(moved, Decimal("11.40"))

    assert start.stop_price_usd == Decimal("9.50")
    assert moved.high_watermark_usd == Decimal("12")
    assert moved.stop_price_usd == Decimal("11.40")
    assert moved.triggered is False
    assert triggered.triggered is True

