from decimal import Decimal

from technicals.indicators import OhlcvCandle
from technicals.vector_engine import build_technical_vector
from utils.results import ResultStatus
from utils.toon import serialize_toon


def test_vector_engine_builds_compact_toon_safe_vector() -> None:
    result = build_technical_vector(
        pair_id="fixture-sol-usdc",
        candles=[
            candle("2026-05-22T11:58:00Z", "4.00", "4.10", "3.95", "4.05", "100"),
            candle("2026-05-22T11:59:00Z", "4.05", "4.20", "4.00", "4.15", "125"),
            candle("2026-05-22T12:00:00Z", "4.15", "4.25", "4.10", "4.20", "150"),
        ],
    )

    assert result.ok is True
    assert result.value == {
        "pair": "fixture-sol-usdc",
        "n": 3,
        "t0": "2026-05-22T11:58:00Z",
        "t1": "2026-05-22T12:00:00Z",
        "px": 4.2,
        "ret": 0.037037,
        "sma": 4.13333333,
        "rng": 0.035714,
        "vol": 375.0,
    }
    assert serialize_toon(result.value) == "\n".join(
        [
            "pair: fixture-sol-usdc",
            "n: 3",
            't0: "2026-05-22T11:58:00Z"',
            't1: "2026-05-22T12:00:00Z"',
            "px: 4.2",
            "ret: 0.037037",
            "sma: 4.13333333",
            "rng: 0.035714",
            "vol: 375.0",
        ]
    )


def test_vector_engine_missing_candles_is_insufficient_data() -> None:
    result = build_technical_vector(pair_id="fixture-sol-usdc", candles=[])

    assert result.status is ResultStatus.INSUFFICIENT_DATA
    assert result.reason_codes == ("OHLCV_CANDLES_MISSING",)


def test_vector_engine_missing_candle_fields_is_insufficient_data() -> None:
    result = build_technical_vector(
        pair_id="fixture-sol-usdc",
        candles=[
            {
                "timestamp": "2026-05-22T12:00:00Z",
                "open": "4.0",
                "high": "4.2",
                "low": "3.9",
                "close": "4.1",
            }
        ],
    )

    assert result.status is ResultStatus.INSUFFICIENT_DATA
    assert result.reason_codes == ("OHLCV_CANDLE_MISSING_FIELDS",)


def candle(
    timestamp: str,
    open_price: str,
    high: str,
    low: str,
    close: str,
    volume: str,
) -> OhlcvCandle:
    return OhlcvCandle(
        timestamp=timestamp,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
    )
