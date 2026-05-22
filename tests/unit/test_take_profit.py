from decimal import Decimal

from execution.take_profit import should_take_profit, take_profit_price


def test_take_profit_triggers_at_twenty_percent_gain() -> None:
    assert take_profit_price(Decimal("10")) == Decimal("12.00")
    assert should_take_profit(Decimal("10"), Decimal("11.99")) is False
    assert should_take_profit(Decimal("10"), Decimal("12.00")) is True

