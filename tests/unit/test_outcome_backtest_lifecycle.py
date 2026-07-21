from datetime import UTC, datetime, timedelta
from decimal import Decimal

from data_pipeline.bitunix_models import BitunixCandle
from intelligence.production_models import ProbabilityState, SignalDecision, SignalDirection
from scoring.backtest_engine import run_walk_forward_backtest
from scoring.outcome_labeler import label_expired_signals
from storage.duckdb_store import DuckDBStore
from storage.market_repository import MarketRepository
from storage.schema import initialize_schema


NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)


def test_outcome_labeler_excludes_overlaps_and_backtest_hash_is_repeatable() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        repository = MarketRepository(store.connection)
        first = _signal("one", NOW)
        overlapping = _signal("two", NOW + timedelta(minutes=1))
        repository.record_signal(first)
        repository.record_signal(overlapping)
        repository.upsert_candles(
            first.instrument_id,
            first.horizon,
            (_candle(NOW + timedelta(minutes=5), high="105", low="97"),),
        )

        report = label_expired_signals(store.connection, now=NOW + timedelta(hours=1))
        one = run_walk_forward_backtest(store.connection, now=NOW + timedelta(hours=2))
        two = run_walk_forward_backtest(store.connection, now=NOW + timedelta(hours=3))

        assert report.labeled == 1
        assert report.skipped_overlap == 1
        assert one is not None and two is not None
        assert one.replay_hash == two.replay_hash
        assert one.no_lookahead_verified
        outcome = store.connection.execute("SELECT target_before_stop FROM outcome_labels").fetchone()
        assert outcome == (False,)  # same candle hits both; stop wins conservatively


def _signal(name: str, generated_at: datetime) -> SignalDecision:
    return SignalDecision(
        signal_id=f"signal-{name}", idempotency_key=f"signal:{name}",
        instrument_id="bitunix:BTCUSDT", direction=SignalDirection.LONG, horizon="5m",
        setup_type="TEST", generated_at=generated_at, expires_at=generated_at + timedelta(minutes=15),
        entry_low=Decimal("99"), entry_high=Decimal("101"), invalidation=Decimal("98"),
        stop=Decimal("98"), targets=(Decimal("104"),), expected_return_pct=2.0, risk_reward=2.0,
        opportunity_score=70, risk_score=25, data_coverage=0.9,
        probability_state=ProbabilityState.UNCALIBRATED, model_version="test",
        liquidity_grade="A", risk_grade="LOW", reasons=("test",), evidence_ids=("evidence",),
    )


def _candle(at: datetime, *, high: str, low: str) -> BitunixCandle:
    return BitunixCandle(
        symbol="BTCUSDT", interval="5m", time=int(at.timestamp() * 1000),
        open="100", high=high, low=low, close="101", quoteVol="1000", baseVol="10",
    )
