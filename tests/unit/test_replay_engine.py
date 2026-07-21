from datetime import UTC, datetime, timedelta
from decimal import Decimal

from data_pipeline.bitunix_models import BitunixCandle
from intelligence.production_models import ProbabilityState, SignalDecision, SignalDirection
from scoring.replay import chronological_walk_forward_splits, replay_signal


NOW = datetime(2026, 7, 20, 12, tzinfo=UTC)


def test_replay_uses_only_forward_candles_and_includes_costs() -> None:
    signal = _signal()
    candles = (
        _candle(NOW - timedelta(minutes=15), 100, 110, 90, 100),
        _candle(NOW + timedelta(minutes=15), 100, 105, 99, 104),
    )

    result = replay_signal(signal, candles)

    assert result.ok and result.value is not None
    assert result.value.target_before_stop is True
    assert result.value.net_return_pct < 4.0
    assert result.value.time_in_trade_seconds == 900


def test_replay_conservatively_counts_stop_when_one_bar_hits_stop_and_target() -> None:
    signal = _signal()
    result = replay_signal(signal, (_candle(NOW + timedelta(minutes=15), 100, 105, 97, 101),))
    assert result.ok and result.value is not None
    assert result.value.target_before_stop is False


def test_walk_forward_splits_never_mix_future_into_training() -> None:
    splits = chronological_walk_forward_splits(700, minimum_train=300, validation_size=100, step=100)
    assert splits
    assert all(max(train) < min(validation) for train, validation in splits)


def _signal() -> SignalDecision:
    return SignalDecision(
        signal_id="signal-replay",
        idempotency_key="signal:replay",
        instrument_id="bitunix:BTCUSDT",
        direction=SignalDirection.LONG,
        horizon="15m",
        setup_type="TEST",
        generated_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        entry_low=Decimal("99.9"),
        entry_high=Decimal("100.1"),
        invalidation=Decimal("98"),
        stop=Decimal("98"),
        targets=(Decimal("104"),),
        expected_return_pct=3.8,
        risk_reward=2,
        opportunity_score=70,
        risk_score=30,
        data_coverage=0.9,
        probability_state=ProbabilityState.UNCALIBRATED,
        model_version="test",
        liquidity_grade="A",
        risk_grade="LOW",
        reasons=("test",),
        evidence_ids=("evidence",),
    )


def _candle(at: datetime, open_price: float, high: float, low: float, close: float) -> BitunixCandle:
    return BitunixCandle(
        symbol="BTCUSDT",
        interval="15m",
        time=int(at.timestamp() * 1000),
        open=open_price,
        high=high,
        low=low,
        close=close,
        quoteVol="1000",
        baseVol="10",
    )
