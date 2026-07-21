"""72-hour collection-only shadow certification state and gate evaluation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from intelligence.production_models import CertificationReport
from scheduler.fault_injection import run_fault_injections
from storage.market_repository import MarketRepository
from storage.schema import EXPECTED_TABLES, list_tables


REQUIRED_SHADOW_HOURS = 72


def start_shadow_certification(
    connection: duckdb.DuckDBPyConnection,
    *,
    now: datetime | None = None,
) -> CertificationReport:
    reference = now or datetime.now(tz=UTC)
    existing = connection.execute(
        "SELECT report_json FROM certification_runs WHERE state IN ('RUNNING', 'INCOMPLETE') ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if existing:
        return CertificationReport.model_validate(json.loads(existing[0]))
    certification_id = f"cert-{uuid4().hex}"
    fault_results = run_fault_injections()
    for name, recovered in fault_results.items():
        connection.execute(
            "INSERT INTO certification_faults VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                f"fault:{certification_id}:{name}", certification_id, reference, name, recovered,
                json.dumps(["FAULT_RECOVERED" if recovered else "FAULT_NOT_RECOVERED"]),
                json.dumps({"deterministic_harness": True, "can_execute_trades": False}),
            ],
        )
    report = CertificationReport(
        certification_id=certification_id,
        started_at=reference,
        evaluated_at=reference,
        elapsed_seconds=0,
        state="RUNNING",
        metrics={"required_hours": float(REQUIRED_SHADOW_HOURS)},
        gate_results={"elapsed_72_hours": False},
        fault_results=fault_results,
        reason_codes=("SHADOW_COLLECTION_STARTED", "PAPER_SIMULATION_DISABLED_REQUIRED"),
    )
    MarketRepository(connection).record_certification(report)
    return report


def evaluate_shadow_certification(
    connection: duckdb.DuckDBPyConnection,
    *,
    database_path: str | Path,
    backup_directory: str | Path,
    now: datetime | None = None,
) -> CertificationReport | None:
    reference = now or datetime.now(tz=UTC)
    row = connection.execute(
        "SELECT certification_id, started_at FROM certification_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    certification_id, started_at = str(row[0]), _aware(row[1])
    elapsed = max(0, int((reference - started_at).total_seconds()))
    faults = {
        str(item[0]): bool(item[1])
        for item in connection.execute(
            "SELECT fault_type, recovered FROM certification_faults WHERE certification_id = ?",
            [certification_id],
        ).fetchall()
    }
    ticker = connection.execute(
        """
        SELECT count(DISTINCT instrument_id), quantile_cont(lag_seconds, 0.95)
        FROM data_health
        WHERE source LIKE 'bitunix%' AND channel = 'ticker' AND checked_at >= ?
        """,
        [started_at],
    ).fetchone()
    candle = connection.execute(
        "SELECT count(DISTINCT instrument_id), max(received_at) FROM market_candles WHERE interval = '1m'"
    ).fetchone()
    unresolved = connection.execute(
        "SELECT count(*) FROM ingestion_gaps WHERE status NOT IN ('RESOLVED') AND detected_at >= ?",
        [started_at],
    ).fetchone()[0]
    invalid_gap_states = connection.execute(
        """
        SELECT count(*) FROM ingestion_gaps
        WHERE detected_at >= ? AND (
            status NOT IN ('DETECTED', 'BACKFILLING', 'RESOLVED', 'UNRESOLVED')
            OR reason_codes_json IS NULL OR reason_codes_json = ''
        )
        """,
        [started_at],
    ).fetchone()[0]
    invalid_signals = connection.execute(
        """
        SELECT count(*) FROM signal_decisions
        WHERE generated_at >= ? AND (
            expires_at <= generated_at OR lower(decision_json) LIKE '%fixture%'
            OR lower(decision_json) LIKE '%preview%'
        )
        """,
        [started_at],
    ).fetchone()[0]
    duplicates = connection.execute(
        "SELECT count(*) - count(DISTINCT idempotency_key) FROM signal_decisions WHERE generated_at >= ?",
        [started_at],
    ).fetchone()[0]
    paper_events = connection.execute(
        "SELECT count(*) FROM paper_order_events WHERE event_at >= ?",
        [started_at],
    ).fetchone()[0]
    heartbeat_failures = connection.execute(
        "SELECT count(*) FROM service_heartbeats WHERE status = 'FAILED' AND heartbeat_at >= ?",
        [started_at],
    ).fetchone()[0]
    restored_backup = _backup_restores(backup_directory)
    replay_hashes = tuple(
        str(item[0]) for item in connection.execute(
            "SELECT replay_hash FROM backtest_runs WHERE replay_hash <> '' ORDER BY completed_at DESC LIMIT 2"
        ).fetchall()
    )
    replay_deterministic = len(replay_hashes) >= 2 and len(set(replay_hashes)) == 1
    ticker_coverage = min(1.0, float(ticker[0] or 0) / 50.0)
    ticker_p95 = float(ticker[1]) if ticker[1] is not None else -1.0
    candle_age = (
        max(0.0, (reference - _aware(candle[1])).total_seconds()) if candle[1] is not None else -1.0
    )
    gates = {
        "elapsed_72_hours": elapsed >= REQUIRED_SHADOW_HOURS * 3600,
        "no_uncaught_service_failure": heartbeat_failures == 0,
        "forced_faults_recovered": bool(faults) and all(faults.values()),
        "top50_core_coverage_95pct": ticker_coverage >= 0.95,
        "ticker_p95_under_15s": 0.0 <= ticker_p95 < 15.0,
        "one_minute_candles_within_two_intervals": 0.0 <= candle_age < 120.0,
        "gaps_visible_or_resolved": invalid_gap_states == 0,
        "no_invalid_live_signals": invalid_signals == 0 and duplicates == 0,
        "paper_simulation_disabled": paper_events == 0,
        "backup_restore": restored_backup,
        "schema_integrity": EXPECTED_TABLES.issubset(list_tables(connection)),
        "deterministic_replay": replay_deterministic,
    }
    passed = all(gates.values())
    state = "PASSED" if passed else "INCOMPLETE" if not gates["elapsed_72_hours"] else "FAILED"
    report = CertificationReport(
        certification_id=certification_id,
        started_at=started_at,
        evaluated_at=reference,
        elapsed_seconds=elapsed,
        state=state,
        metrics={
            "ticker_coverage": ticker_coverage,
            "ticker_p95_age_seconds": ticker_p95,
            "candle_age_seconds": candle_age,
            "unresolved_gaps": float(unresolved),
            "invalid_signals": float(invalid_signals),
            "duplicate_signals": float(duplicates),
        },
        gate_results=gates,
        fault_results=faults,
        replay_hashes=replay_hashes,
        reason_codes=(
            "SHADOW_CERTIFICATION_PASSED" if passed else "SHADOW_CERTIFICATION_GATES_OPEN",
            "NO_REAL_MONEY_EXECUTION",
        ),
    )
    MarketRepository(connection).record_certification(report)
    return report


def _backup_restores(directory: str | Path) -> bool:
    paths = sorted(Path(directory).glob("traidr-*.duckdb"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        return False
    try:
        with duckdb.connect(str(paths[0]), read_only=True) as restored:
            return EXPECTED_TABLES.issubset(list_tables(restored))
    except duckdb.Error:
        return False


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
