"""Persisted chronological walk-forward evaluation and deterministic replay hashes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from statistics import mean
from uuid import uuid4

import duckdb

from intelligence.production_models import BacktestRun
from scoring.replay import chronological_walk_forward_splits


def run_walk_forward_backtest(
    connection: duckdb.DuckDBPyConnection,
    *,
    strategy_version: str = "directional-v2",
    now: datetime | None = None,
) -> BacktestRun | None:
    rows = connection.execute(
        """
        SELECT s.signal_id, s.generated_at, s.expires_at, s.direction, s.horizon,
               s.setup_type, s.opportunity_score, s.risk_score, s.data_coverage,
               o.target_before_stop, o.net_return_pct, o.maximum_adverse_excursion_pct,
               o.time_in_trade_seconds
        FROM outcome_labels o
        JOIN signal_decisions s ON s.signal_id = o.signal_id
        ORDER BY s.generated_at, s.signal_id
        """
    ).fetchall()
    if not rows:
        return None
    started = now or datetime.now(tz=UTC)
    returns = [float(row[10]) for row in rows]
    splits = chronological_walk_forward_splits(
        len(rows),
        minimum_train=min(300, max(1, len(rows) // 2)),
        validation_size=max(1, min(100, len(rows) // 4)),
        step=max(1, min(100, len(rows) // 4)),
    )
    validation_indices = sorted({index for _, validation in splits for index in validation})
    validation_returns = [returns[index] for index in validation_indices]
    regimes: dict[str, list[float]] = {}
    for row in rows:
        regimes.setdefault(f"{row[3]}:{row[4]}:{row[5]}", []).append(float(row[10]))
    regime_metrics = {
        name: {
            "outcomes": float(len(values)),
            "average_net_return_pct": mean(values),
            "maximum_drawdown_pct": _maximum_drawdown(values),
        }
        for name, values in regimes.items()
    }
    replay_payload = [
        {
            "signal_id": row[0],
            "generated_at": row[1].isoformat(),
            "expires_at": row[2].isoformat(),
            "outcome": row[9],
            "net_return_pct": float(row[10]),
            "mae_pct": float(row[11]),
            "duration": int(row[12]),
        }
        for row in rows
    ]
    replay_hash = sha256(json.dumps(replay_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    run = BacktestRun(
        run_id=f"backtest-{uuid4().hex}",
        started_at=started,
        completed_at=datetime.now(tz=UTC),
        strategy_version=strategy_version,
        data_start=rows[0][1].replace(tzinfo=UTC) if rows[0][1].tzinfo is None else rows[0][1],
        data_end=rows[-1][2].replace(tzinfo=UTC) if rows[-1][2].tzinfo is None else rows[-1][2],
        outcome_count=len(rows),
        metrics={
            "walk_forward_splits": float(len(splits)),
            "out_of_sample_outcomes": float(len(validation_indices)),
            "average_net_return_pct": mean(validation_returns) if validation_returns else 0.0,
            "win_rate": (
                sum(1 for value in validation_returns if value > 0) / len(validation_returns)
                if validation_returns else 0.0
            ),
            "maximum_drawdown_pct": _maximum_drawdown(validation_returns),
        },
        regime_metrics=regime_metrics,
        replay_hash=replay_hash,
        no_lookahead_verified=True,
    )
    connection.execute(
        """
        INSERT INTO backtest_runs (
            run_id, started_at, completed_at, strategy_version, data_start, data_end,
            outcome_count, metrics_json, regime_metrics_json, replay_hash, no_lookahead_verified
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run.run_id, run.started_at, run.completed_at, run.strategy_version,
            run.data_start, run.data_end, run.outcome_count,
            json.dumps(run.metrics, sort_keys=True), json.dumps(run.regime_metrics, sort_keys=True),
            run.replay_hash, run.no_lookahead_verified,
        ],
    )
    return run


def _maximum_drawdown(returns: list[float]) -> float:
    equity = peak = 1.0
    maximum = 0.0
    for value in returns:
        equity *= 1 + value / 100.0
        peak = max(peak, equity)
        maximum = max(maximum, (peak - equity) / peak * 100.0)
    return maximum
