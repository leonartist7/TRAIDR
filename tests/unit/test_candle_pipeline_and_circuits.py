from datetime import UTC, datetime, timedelta
from decimal import Decimal

from data_pipeline.bitunix_models import BitunixCandle
from data_pipeline.candle_pipeline import OneMinuteCandlePipeline, aggregate_candles
from data_pipeline.provider_runtime import ProviderCircuitBreaker
from intelligence.production_models import (
    CircuitStatus,
    DataMode,
    EventQuality,
    IngestionGapStatus,
    MarketChannel,
    MarketEvent,
)


NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)


def test_one_minute_gap_is_persistable_and_complete_aggregation_is_exact() -> None:
    pipeline = OneMinuteCandlePipeline()
    first = _event(NOW, Decimal("100"))
    later = _event(NOW + timedelta(minutes=3), Decimal("103"))

    pipeline.ingest(first)
    _, gap = pipeline.ingest(later)
    candles = tuple(_candle(index) for index in range(5))
    aggregate = aggregate_candles(candles, "5m")

    assert gap is not None and gap.status is IngestionGapStatus.DETECTED
    assert gap.gap_start == NOW + timedelta(minutes=1)
    assert gap.gap_end == NOW + timedelta(minutes=2)
    assert len(aggregate) == 1
    assert aggregate[0].open == Decimal("100")
    assert aggregate[0].close == Decimal("104.5")
    assert aggregate_candles(candles[:-1], "5m") == ()


def test_provider_circuit_opens_and_half_opens_after_retry() -> None:
    circuit = ProviderCircuitBreaker("provider", "channel", failure_threshold=2, recovery_seconds=10)
    circuit.failure(now=NOW)
    circuit.failure(now=NOW)

    assert circuit.state is CircuitStatus.OPEN
    assert not circuit.allow(NOW + timedelta(seconds=5))
    assert circuit.allow(NOW + timedelta(seconds=11))
    assert circuit.state is CircuitStatus.HALF_OPEN
    circuit.success()
    assert circuit.state is CircuitStatus.CLOSED


def _event(at: datetime, close: Decimal) -> MarketEvent:
    timestamp = int(at.timestamp() * 1000)
    return MarketEvent(
        event_id=f"event-{timestamp}", idempotency_key=f"key-{timestamp}",
        data_mode=DataMode.LIVE_PUBLIC, source="bitunix_public_ws",
        instrument_id="bitunix:BTCUSDT", channel=MarketChannel.KLINE,
        event_at=at, received_at=at, schema_fingerprint="schema",
        quality=EventQuality.SUFFICIENT, reason_codes=("TEST",),
        payload={
            "channel": "market_kline_1min", "symbol": "BTCUSDT",
            "data": {"t": timestamp, "o": str(close), "h": str(close + 1),
                     "l": str(close - 1), "c": str(close), "b": "10", "q": "1000"},
        },
    )


def _candle(index: int) -> BitunixCandle:
    value = Decimal("100") + index
    return BitunixCandle(
        symbol="BTCUSDT", interval="1m", time=int((NOW + timedelta(minutes=index)).timestamp() * 1000),
        open=value, high=value + 1, low=value - 1, close=value + Decimal("0.5"),
        quoteVol="1000", baseVol="10",
    )
