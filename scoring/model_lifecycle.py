"""Nightly side/horizon champion-challenger training and local artifact persistence."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import duckdb

from intelligence.production_models import CalibrationReport, SignalDirection
from scoring.artifact_store import write_model_artifact
from scoring.model_training import train_champion_challenger
from storage.market_repository import MarketRepository


def train_eligible_buckets(
    connection: duckdb.DuckDBPyConnection,
    *,
    artifact_root: str | Path,
    now: datetime | None = None,
) -> dict[str, tuple[str, ...]]:
    reference = now or datetime.now(tz=UTC)
    rows = connection.execute(
        """
        SELECT s.signal_id, s.instrument_id, s.direction, s.horizon, s.generated_at,
               s.setup_type, o.target_before_stop, o.net_return_pct
        FROM outcome_labels o
        JOIN signal_decisions s ON s.signal_id = o.signal_id
        WHERE s.direction IN ('LONG', 'SHORT') AND o.target_before_stop IS NOT NULL
        ORDER BY s.generated_at
        """
    ).fetchall()
    buckets: dict[tuple[str, str], list[tuple[dict[str, float], bool, datetime, float, str]]] = defaultdict(list)
    for row in rows:
        feature_row = connection.execute(
            """
            SELECT features_json, feature_version, regime
            FROM feature_snapshots
            WHERE instrument_id = ? AND horizon = ? AND observed_at <= ?
            ORDER BY observed_at DESC LIMIT 1
            """,
            [row[1], row[3], row[4]],
        ).fetchone()
        if feature_row is None:
            continue
        features = json.loads(feature_row[0])
        numeric = {str(key): float(value) for key, value in features.items() if isinstance(value, (int, float))}
        numeric.update({"opportunity_context": 1.0})
        net_return = float(row[7])
        buckets[(row[2], row[3])].append(
            (numeric, bool(row[6]) and net_return > 0.0, _aware(row[4]), net_return, str(feature_row[2]))
        )
    results: dict[str, tuple[str, ...]] = {}
    repository = MarketRepository(connection)
    for (direction_value, horizon), samples in buckets.items():
        horizon_literal = cast(Literal["5m", "15m", "1h", "4h", "1d"], horizon)
        bucket_name = f"{direction_value}:{horizon}"
        training = train_champion_challenger(
            [sample[0] for sample in samples],
            [sample[1] for sample in samples],
            [sample[2] for sample in samples],
            net_returns=[sample[3] for sample in samples],
            regimes=[sample[4] for sample in samples],
            current_champion_metrics=_current_metrics(connection, direction_value, horizon),
        )
        if not training.ok or training.value is None:
            results[bucket_name] = training.reason_codes
            continue
        report = training.value
        version = reference.strftime("%Y%m%dT%H%M%SZ")
        model_id = f"directional-{direction_value.lower()}-{horizon}"
        previous = connection.execute(
            """
            SELECT artifact_id FROM model_artifact_manifests
            WHERE model_id = ? AND active = TRUE ORDER BY created_at DESC LIMIT 1
            """,
            [model_id],
        ).fetchone()
        manifest = write_model_artifact(
            report,
            model_id=model_id,
            version=version,
            direction=SignalDirection(direction_value),
            horizon=horizon_literal,
            feature_version="multi-horizon-v1",
            root=artifact_root,
            rollback_artifact_id=str(previous[0]) if previous else None,
        )
        if manifest.active:
            connection.execute(
                "UPDATE model_artifact_manifests SET active = FALSE WHERE model_id = ? AND active = TRUE",
                [model_id],
            )
        repository.record_model_artifact(manifest)
        sample_size = report.test_samples
        calibration = CalibrationReport(
            calibration_id=f"calibration:{model_id}:{version}",
            direction=SignalDirection(direction_value),
            horizon=horizon_literal,
            sample_size=sample_size,
            brier_score=report.champion_brier,
            expected_calibration_error=report.champion_ece,
            method="isotonic" if report.validation_samples >= 2000 else "sigmoid",
            eligible_for_display=(
                manifest.active and sample_size >= 500 and report.champion_ece <= 0.05
            ),
            generated_at=reference,
            reason_codes=(
                "CALIBRATION_DISPLAY_ELIGIBLE"
                if manifest.active and sample_size >= 500 and report.champion_ece <= 0.05
                else "CALIBRATION_DISPLAY_BLOCKED",
                "INDEPENDENT_OUT_OF_SAMPLE_ONLY",
            ),
        )
        repository.record_calibration_report(calibration)
        results[bucket_name] = manifest.reason_codes
    return results


def _current_metrics(
    connection: duckdb.DuckDBPyConnection,
    direction: str,
    horizon: str,
) -> dict[str, float] | None:
    row = connection.execute(
        """
        SELECT metrics_json FROM model_artifact_manifests
        WHERE direction = ? AND horizon = ? AND active = TRUE
        ORDER BY created_at DESC LIMIT 1
        """,
        [direction, horizon],
    ).fetchone()
    if row is None:
        return None
    metrics = json.loads(row[0])
    return {
        "brier": float(metrics.get("champion_brier", float("inf"))),
        "net_return_after_costs": float(metrics.get("net_return_after_costs", float("-inf"))),
        "maximum_drawdown": float(metrics.get("maximum_drawdown", float("inf"))),
        "regime_stability": float(metrics.get("regime_stability", float("-inf"))),
    }


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
