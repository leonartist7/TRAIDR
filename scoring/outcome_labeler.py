"""Continuous, conservative outcome labeling from future data only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import duckdb

from data_pipeline.bitunix_models import BitunixCandle
from intelligence.production_models import SignalDecision
from scoring.replay import replay_signal
from storage.market_repository import MarketRepository


@dataclass(frozen=True)
class OutcomeLabelingReport:
    evaluated: int
    labeled: int
    skipped_overlap: int
    insufficient: int
    reason_codes: tuple[str, ...]


def label_expired_signals(
    connection: duckdb.DuckDBPyConnection,
    *,
    now: datetime | None = None,
) -> OutcomeLabelingReport:
    reference = now or datetime.now(tz=UTC)
    rows = connection.execute(
        """
        SELECT s.decision_json
        FROM signal_decisions s
        LEFT JOIN outcome_labels o ON o.signal_id = s.signal_id
        WHERE o.signal_id IS NULL AND s.expires_at <= ? AND s.direction <> 'NO_TRADE'
        ORDER BY s.generated_at, s.instrument_id, s.direction, s.horizon, s.setup_type
        """,
        [reference],
    ).fetchall()
    repository = MarketRepository(connection)
    last_independent_expiry: dict[tuple[str, str, str, str], datetime] = {}
    evaluated = labeled = overlap = insufficient = 0
    for row in rows:
        evaluated += 1
        signal = SignalDecision.model_validate(json.loads(row[0]))
        bucket = (signal.instrument_id, signal.direction.value, signal.horizon, signal.setup_type)
        previous_expiry = last_independent_expiry.get(bucket)
        if previous_expiry is not None and signal.generated_at < previous_expiry:
            overlap += 1
            continue
        candles = _forward_candles(connection, signal)
        result = replay_signal(signal, candles)
        if not result.ok or result.value is None:
            insufficient += 1
            continue
        label = result.value.model_copy(
            update={
                "reason_codes": (*result.value.reason_codes, "INDEPENDENT_OUT_OF_SAMPLE_OUTCOME"),
            }
        )
        if repository.record_outcome(label):
            labeled += 1
            last_independent_expiry[bucket] = signal.expires_at
    return OutcomeLabelingReport(
        evaluated=evaluated,
        labeled=labeled,
        skipped_overlap=overlap,
        insufficient=insufficient,
        reason_codes=("FUTURE_CANDLES_ONLY", "SAME_CANDLE_STOP_FIRST", "OVERLAPPING_OUTCOMES_EXCLUDED"),
    )


def _forward_candles(
    connection: duckdb.DuckDBPyConnection,
    signal: SignalDecision,
) -> tuple[BitunixCandle, ...]:
    rows = connection.execute(
        """
        SELECT open_time_ms, open, high, low, close, quote_volume, base_volume
        FROM market_candles
        WHERE instrument_id = ? AND interval = ?
          AND open_time_ms > ? AND open_time_ms <= ? AND quality = 'sufficient'
        ORDER BY open_time_ms
        """,
        [
            signal.instrument_id,
            signal.horizon,
            int(signal.generated_at.timestamp() * 1000),
            int(signal.expires_at.timestamp() * 1000),
        ],
    ).fetchall()
    symbol = signal.instrument_id.split(":", 1)[-1]
    return tuple(
        BitunixCandle(
            symbol=symbol,
            interval=signal.horizon,
            time_ms=row[0],
            open=row[1], high=row[2], low=row[3], close=row[4],
            quote_volume=row[5], base_volume=row[6],
        )
        for row in rows
    )
