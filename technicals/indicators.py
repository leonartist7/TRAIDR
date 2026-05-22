"""Deterministic indicators over local OHLCV candles."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class OhlcvCandle:
    """One validated local OHLCV candle."""

    timestamp: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def simple_moving_average(values: Iterable[Decimal]) -> Decimal:
    samples = tuple(values)
    if not samples:
        raise ValueError("moving average requires at least one value")
    return sum(samples, Decimal("0")) / Decimal(len(samples))


def close_return(start: Decimal, end: Decimal) -> Decimal:
    if start <= Decimal("0"):
        raise ValueError("return baseline must be positive")
    return (end - start) / start


def candle_range(high: Decimal, low: Decimal, close: Decimal) -> Decimal:
    if close <= Decimal("0"):
        raise ValueError("range denominator must be positive")
    return (high - low) / close


def total_volume(candles: Iterable[OhlcvCandle]) -> Decimal:
    return sum((candle.volume for candle in candles), Decimal("0"))

