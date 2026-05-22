"""Compact TOON-safe technical vectors from deterministic OHLCV candles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, TypeAlias

from technicals.indicators import (
    OhlcvCandle,
    candle_range,
    close_return,
    simple_moving_average,
    total_volume,
)
from utils.results import Result
from utils.toon import JsonValue, assert_safe_payload

RawCandle: TypeAlias = OhlcvCandle | Mapping[str, Any]
_REQUIRED_FIELDS = ("timestamp", "open", "high", "low", "close", "volume")
_PRICE_QUANTUM = Decimal("0.00000001")
_RATIO_QUANTUM = Decimal("0.000001")


def build_technical_vector(
    *,
    pair_id: str,
    candles: Sequence[RawCandle] | None,
) -> Result[dict[str, JsonValue]]:
    """Build a compact safe vector or fail closed when candles are unavailable."""

    if not candles:
        return Result.insufficient_data("OHLCV_CANDLES_MISSING")
    if not pair_id.strip():
        return Result.insufficient_data("PAIR_ID_MISSING")

    validated = _validate_candles(candles)
    if not validated.ok or validated.value is None:
        return Result.insufficient_data(*validated.reason_codes)

    prepared = validated.value
    first = prepared[0]
    last = prepared[-1]
    closes = tuple(candle.close for candle in prepared)
    vector: dict[str, JsonValue] = {
        "pair": pair_id,
        "n": len(prepared),
        "t0": first.timestamp,
        "t1": last.timestamp,
        "px": _number(last.close, _PRICE_QUANTUM),
        "ret": _number(close_return(first.close, last.close), _RATIO_QUANTUM),
        "sma": _number(simple_moving_average(closes), _PRICE_QUANTUM),
        "rng": _number(candle_range(last.high, last.low, last.close), _RATIO_QUANTUM),
        "vol": _number(total_volume(prepared), _PRICE_QUANTUM),
    }
    assert_safe_payload(vector)
    return Result.success(vector)


def _validate_candles(candles: Sequence[RawCandle]) -> Result[tuple[OhlcvCandle, ...]]:
    prepared: list[OhlcvCandle] = []
    for raw in candles:
        candle_result = _coerce_candle(raw)
        if not candle_result.ok or candle_result.value is None:
            return Result.insufficient_data(*candle_result.reason_codes)
        prepared.append(candle_result.value)
    return Result.success(tuple(prepared))


def _coerce_candle(raw: RawCandle) -> Result[OhlcvCandle]:
    if isinstance(raw, OhlcvCandle):
        return _validate_candle(raw)
    if not isinstance(raw, Mapping):
        return Result.insufficient_data("OHLCV_CANDLE_MALFORMED")
    if any(field not in raw or raw[field] is None for field in _REQUIRED_FIELDS):
        return Result.insufficient_data("OHLCV_CANDLE_MISSING_FIELDS")

    try:
        candle = OhlcvCandle(
            timestamp=str(raw["timestamp"]).strip(),
            open=_decimal(raw["open"]),
            high=_decimal(raw["high"]),
            low=_decimal(raw["low"]),
            close=_decimal(raw["close"]),
            volume=_decimal(raw["volume"]),
        )
    except (InvalidOperation, TypeError, ValueError):
        return Result.insufficient_data("OHLCV_CANDLE_MALFORMED")
    return _validate_candle(candle)


def _validate_candle(candle: OhlcvCandle) -> Result[OhlcvCandle]:
    if not candle.timestamp:
        return Result.insufficient_data("OHLCV_TIMESTAMP_MISSING")
    if min(candle.open, candle.high, candle.low, candle.close) <= Decimal("0"):
        return Result.insufficient_data("OHLCV_PRICE_INVALID")
    if candle.volume < Decimal("0"):
        return Result.insufficient_data("OHLCV_VOLUME_INVALID")
    if candle.high < max(candle.open, candle.close) or candle.low > min(
        candle.open,
        candle.close,
    ):
        return Result.insufficient_data("OHLCV_RANGE_INVALID")
    if candle.low > candle.high:
        return Result.insufficient_data("OHLCV_RANGE_INVALID")
    return Result.success(candle)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _number(value: Decimal, quantum: Decimal) -> float:
    return float(value.quantize(quantum, rounding=ROUND_HALF_UP))

