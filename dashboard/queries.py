"""Read-only DuckDB queries for the local Streamlit dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import yaml

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"
DEFAULT_LIMIT = 20
MARKET_CANDLE_INTERVALS = frozenset({"1m", "5m", "15m", "1h", "4h", "1d"})


@dataclass(frozen=True)
class DashboardData:
    """All read-only dashboard sections fetched from local storage."""

    database_path: Path
    database_exists: bool
    tables: set[str]
    market_snapshots: list[dict[str, Any]]
    market_radar: list[dict[str, Any]]
    scan_evidence: list[dict[str, Any]]
    token_details: list[dict[str, Any]]
    watchlist_entries: list[dict[str, Any]]
    portfolio_entries: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    reports: list[dict[str, Any]]
    technical_vectors: list[dict[str, Any]]
    anti_rug_status: list[dict[str, Any]]
    risk_decisions: list[dict[str, Any]]
    simulated_orders: list[dict[str, Any]]
    simulated_fills: list[dict[str, Any]]
    audit_events: list[dict[str, Any]]
    safety_status: dict[str, Any]
    signal_decisions: list[dict[str, Any]] = field(default_factory=list)
    data_health: list[dict[str, Any]] = field(default_factory=list)
    service_heartbeats: list[dict[str, Any]] = field(default_factory=list)
    paper_futures_positions: list[dict[str, Any]] = field(default_factory=list)
    paper_futures_portfolios: list[dict[str, Any]] = field(default_factory=list)
    calibration_reports: list[dict[str, Any]] = field(default_factory=list)
    feature_snapshots: list[dict[str, Any]] = field(default_factory=list)
    evidence_bundles: list[dict[str, Any]] = field(default_factory=list)
    market_microstructure: list[dict[str, Any]] = field(default_factory=list)
    news_evidence: list[dict[str, Any]] = field(default_factory=list)
    onchain_evidence: list[dict[str, Any]] = field(default_factory=list)
    ingestion_gaps: list[dict[str, Any]] = field(default_factory=list)
    provider_circuits: list[dict[str, Any]] = field(default_factory=list)
    paper_futures_orders: list[dict[str, Any]] = field(default_factory=list)
    paper_futures_fills: list[dict[str, Any]] = field(default_factory=list)
    paper_funding_events: list[dict[str, Any]] = field(default_factory=list)
    paper_order_events: list[dict[str, Any]] = field(default_factory=list)
    paper_stress_snapshots: list[dict[str, Any]] = field(default_factory=list)
    model_artifacts: list[dict[str, Any]] = field(default_factory=list)
    certification_runs: list[dict[str, Any]] = field(default_factory=list)
    decision_audit: list[dict[str, Any]] = field(default_factory=list)
    scanner_scores: list[dict[str, Any]] = field(default_factory=list)
    shadow_evidence: list[dict[str, Any]] = field(default_factory=list)


def configured_database_path() -> Path:
    """Return the configured local DuckDB path from settings.yaml."""

    with SETTINGS_PATH.open(encoding="utf-8") as settings_file:
        settings = yaml.safe_load(settings_file)
    raw_path = Path(settings["storage"]["local_database_path"])
    return raw_path if raw_path.is_absolute() else SETTINGS_PATH.parents[1] / raw_path


def load_dashboard_data(
    database_path: str | Path | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
) -> DashboardData:
    """Load all dashboard sections without creating or mutating the database."""

    path = Path(database_path) if database_path is not None else configured_database_path()
    path = path if path.is_absolute() else SETTINGS_PATH.parents[1] / path
    safety = load_safety_status()
    if not path.exists():
        return DashboardData(
            database_path=path,
            database_exists=False,
            tables=set(),
            market_snapshots=[],
            market_radar=[],
            scan_evidence=[],
            token_details=[],
            watchlist_entries=[],
            portfolio_entries=[],
            alerts=[],
            reports=[],
            technical_vectors=[],
            anti_rug_status=[],
            risk_decisions=[],
            simulated_orders=[],
            simulated_fills=[],
            audit_events=[],
            safety_status=safety,
        )

    with duckdb.connect(database=str(path), read_only=True) as connection:
        tables = _list_tables(connection)
        return DashboardData(
            database_path=path,
            database_exists=True,
            tables=tables,
            market_snapshots=_query_if_table(
                connection,
                tables,
                "evidence_snapshots",
                """
                SELECT snapshot_id, source_name, observed_at, collected_at, quality_status,
                       payload_json, provenance_json
                FROM evidence_snapshots
                ORDER BY collected_at DESC
                LIMIT ?
                """,
                limit,
            ),
            market_radar=_query_if_table(
                connection,
                tables,
                "opportunity_radar_states",
                """
                WITH latest AS (
                    SELECT subject_id, state, rank, risk_score, opportunity_score, confidence,
                           reason_codes_json, payload_json, recorded_at,
                           row_number() OVER (
                               PARTITION BY subject_id ORDER BY recorded_at DESC, radar_state_id DESC
                           ) AS row_number
                    FROM opportunity_radar_states
                    WHERE recorded_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                      AND lower(subject_id) NOT LIKE 'fixture-%'
                      AND lower(payload_json) NOT LIKE '%"data_mode":"fixture"%'
                )
                SELECT subject_id, state, rank, risk_score, opportunity_score, confidence,
                       reason_codes_json, payload_json, recorded_at
                FROM latest
                WHERE row_number = 1
                ORDER BY opportunity_score - risk_score DESC, recorded_at DESC
                LIMIT ?
                """,
                limit,
            ),
            scan_evidence=_query_if_table(
                connection,
                tables,
                "evidence_snapshots",
                """
                SELECT snapshot_id, source_name, observed_at, collected_at, quality_status,
                       payload_json, provenance_json
                FROM evidence_snapshots
                WHERE source_name LIKE 'market_scan:%'
                ORDER BY collected_at DESC
                LIMIT ?
                """,
                limit,
            ),
            token_details=_query_if_table(
                connection,
                tables,
                "evidence_snapshots",
                """
                SELECT snapshot_id, source_name, observed_at, collected_at, quality_status,
                       payload_json, provenance_json
                FROM evidence_snapshots
                WHERE source_name LIKE 'market_scan:%'
                   OR source_name LIKE 'token_detail:%'
                ORDER BY collected_at DESC
                LIMIT ?
                """,
                limit,
            ),
            watchlist_entries=_query_if_table(
                connection,
                tables,
                "watchlist_entries",
                """
                SELECT pair_ref, note, tags_json, created_at, updated_at, active
                FROM watchlist_entries
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                limit,
            ),
            portfolio_entries=_query_if_table(
                connection,
                tables,
                "manual_portfolio_entries",
                """
                SELECT entry_id, symbol, chain, pair_ref, entry_price, size_usd,
                       conviction, risk_level, active, updated_at
                FROM manual_portfolio_entries
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                limit,
            ),
            alerts=_query_if_table(
                connection,
                tables,
                "notification_alerts",
                """
                SELECT alert_id, recorded_at, subject_id, channel, severity, status,
                       reason_codes_json, payload_json
                FROM notification_alerts
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                limit,
            ),
            reports=_query_if_table(
                connection,
                tables,
                "research_reports",
                """
                SELECT report_id, recorded_at, report_type, status, reason_codes_json,
                       payload_json
                FROM research_reports
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                limit,
            ),
            technical_vectors=_query_if_table(
                connection,
                tables,
                "technical_vectors",
                """
                SELECT vector_id, snapshot_id, created_at, feature_status, features_json
                FROM technical_vectors
                ORDER BY created_at DESC
                LIMIT ?
                """,
                limit,
            ),
            anti_rug_status=_query_if_table(
                connection,
                tables,
                "evidence_snapshots",
                """
                SELECT snapshot_id, source_name, observed_at, quality_status, payload_json
                FROM evidence_snapshots
                WHERE lower(payload_json) LIKE '%anti%'
                   OR lower(payload_json) LIKE '%rug%'
                   OR lower(payload_json) LIKE '%liquidity%'
                   OR lower(payload_json) LIKE '%holder%'
                ORDER BY collected_at DESC
                LIMIT ?
                """,
                limit,
            ),
            risk_decisions=_query_if_table(
                connection,
                tables,
                "risk_decisions",
                """
                SELECT decision_id, intent_id, decided_at, decision, reason_codes_json, details_json
                FROM risk_decisions
                ORDER BY decided_at DESC
                LIMIT ?
                """,
                limit,
            ),
            simulated_orders=_query_if_table(
                connection,
                tables,
                "simulated_orders",
                """
                SELECT order_id, risk_decision_id, created_at, side, pair_id, notional_usd,
                       order_status, metadata_json
                FROM simulated_orders
                ORDER BY created_at DESC
                LIMIT ?
                """,
                limit,
            ),
            simulated_fills=_query_if_table(
                connection,
                tables,
                "simulated_fills",
                """
                SELECT fill_id, order_id, filled_at, quantity, price_usd, notional_usd,
                       metadata_json
                FROM simulated_fills
                ORDER BY filled_at DESC
                LIMIT ?
                """,
                limit,
            ),
            audit_events=_query_if_table(
                connection,
                tables,
                "audit_events",
                """
                SELECT event_id, recorded_at, event_type, severity, reason_codes_json,
                       payload_json
                FROM audit_events
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                limit,
            ),
            safety_status=safety,
            signal_decisions=_query_if_table(
                connection,
                tables,
                "signal_decisions",
                """
                WITH latest AS (
                    SELECT signal_id, instrument_id, direction, horizon, setup_type,
                           generated_at, expires_at, opportunity_score, risk_score,
                           data_coverage, probability_state, success_probability,
                           calibration_sample_size, model_version, decision_json,
                           row_number() OVER (
                               PARTITION BY instrument_id, horizon ORDER BY generated_at DESC, signal_id DESC
                           ) AS row_number
                    FROM signal_decisions
                    WHERE expires_at > CURRENT_TIMESTAMP
                )
                SELECT * EXCLUDE (row_number)
                FROM latest
                WHERE row_number = 1
                ORDER BY opportunity_score - risk_score DESC, generated_at DESC
                LIMIT ?
                """,
                limit,
            ),
            data_health=_query_if_table(
                connection,
                tables,
                "data_health",
                """
                SELECT source, instrument_id, channel, checked_at,
                       CASE
                           WHEN checked_at < CURRENT_TIMESTAMP - INTERVAL '30 seconds' THEN 'STALE'
                           ELSE status
                       END AS status,
                       last_event_at,
                       lag_seconds, reconnect_count, gap_count, coverage, reason_codes_json
                FROM data_health
                ORDER BY CASE
                             WHEN checked_at < CURRENT_TIMESTAMP - INTERVAL '30 seconds' THEN 0
                             WHEN status = 'DOWN' THEN 1
                             WHEN status = 'DEGRADED' THEN 2
                             ELSE 3
                         END,
                         checked_at DESC
                LIMIT ?
                """,
                limit,
            ),
            service_heartbeats=_query_if_table(
                connection,
                tables,
                "service_heartbeats",
                """
                SELECT service_name, process_id, started_at, heartbeat_at,
                       CASE
                           WHEN status = 'RUNNING'
                            AND heartbeat_at < CURRENT_TIMESTAMP - INTERVAL '30 seconds'
                           THEN 'STALE'
                           ELSE status
                       END AS status,
                       data_mode, details_json
                FROM service_heartbeats
                ORDER BY heartbeat_at DESC
                LIMIT ?
                """,
                limit,
            ),
            paper_futures_positions=_query_if_table(
                connection,
                tables,
                "paper_futures_positions",
                """
                SELECT position_id, instrument_id, direction, opened_at, updated_at, status, position_json
                FROM paper_futures_positions
                ORDER BY CASE status WHEN 'OPEN' THEN 0 ELSE 1 END, updated_at DESC
                LIMIT ?
                """,
                limit,
            ),
            paper_futures_portfolios=_query_if_table(
                connection,
                tables,
                "paper_futures_portfolios",
                """
                SELECT portfolio_snapshot_id, captured_at, equity_usd, cash_usd,
                       used_margin_usd, daily_pnl_usd, halted, snapshot_json
                FROM paper_futures_portfolios
                ORDER BY captured_at DESC
                LIMIT ?
                """,
                limit,
            ),
            calibration_reports=_query_if_table(
                connection,
                tables,
                "calibration_reports",
                """
                SELECT calibration_id, direction, horizon, generated_at, sample_size,
                       brier_score, expected_calibration_error, method,
                       eligible_for_display, reason_codes_json
                FROM calibration_reports
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                limit,
            ),
            feature_snapshots=_query_if_table(
                connection, tables, "feature_snapshots",
                """
                SELECT feature_id, instrument_id, horizon, observed_at, regime,
                       data_coverage, features_json, missing_features_json,
                       quality_warnings_json, contradiction_flags_json, evidence_ids_json
                FROM feature_snapshots ORDER BY calculated_at DESC LIMIT ?
                """, limit,
            ),
            evidence_bundles=_query_if_table(
                connection, tables, "evidence_bundles",
                """
                SELECT bundle_id, instrument_id, canonical_asset_id, observed_at,
                       data_coverage, hard_vetoes_json, reason_codes_json, bundle_json
                FROM evidence_bundles ORDER BY generated_at DESC LIMIT ?
                """, limit,
            ),
            scanner_scores=_query_if_table(
                connection, tables, "market_scanner_scores",
                """
                SELECT score_id, instrument_id, observed_at, recorded_at, status, direction,
                       score, long_score, short_score, risk_score, conflicts_json,
                       reason_codes_json, factor_breakdown_json
                FROM market_scanner_scores
                ORDER BY observed_at DESC, recorded_at DESC
                LIMIT ?
                """, limit,
            ),
            shadow_evidence=_query_if_table(
                connection, tables, "shadow_market_evidence",
                """
                SELECT shadow_evidence_id, instrument_id, provider, observed_at, received_at,
                       recorded_at, fields_json, metadata_json, reason_codes_json,
                       assessment_json, shadow_only, scoring_weight, can_execute_trades
                FROM shadow_market_evidence
                ORDER BY observed_at DESC, recorded_at DESC
                LIMIT ?
                """, limit,
            ),
            market_microstructure=_query_if_table(
                connection, tables, "market_microstructure",
                """
                SELECT metric_id, instrument_id, observed_at, bid_price, ask_price,
                       spread_bps, depth_imbalance, trade_delta, basis_bps, funding_rate, payload_json
                FROM market_microstructure ORDER BY observed_at DESC LIMIT ?
                """, limit,
            ),
            news_evidence=_query_if_table(
                connection, tables, "news_evidence",
                """
                SELECT evidence_id, canonical_asset_id, source, headline, url, published_at,
                       reliability, relevance, age_weight, mapping_state, reason_codes_json
                FROM news_evidence ORDER BY observed_at DESC LIMIT ?
                """, limit,
            ),
            onchain_evidence=_query_if_table(
                connection, tables, "onchain_evidence",
                """
                SELECT evidence_id, canonical_asset_id, source, chain_id, contract_address,
                       observed_at, coverage, hard_vetoes_json, reason_codes_json, evidence_json
                FROM onchain_evidence ORDER BY observed_at DESC LIMIT ?
                """, limit,
            ),
            ingestion_gaps=_query_if_table(
                connection, tables, "ingestion_gaps",
                """
                SELECT gap_id, source, instrument_id, channel, interval, detected_at,
                       gap_start, gap_end, status, attempts, updated_at, reason_codes_json
                FROM ingestion_gaps ORDER BY updated_at DESC NULLS LAST LIMIT ?
                """, limit,
            ),
            provider_circuits=_query_if_table(
                connection, tables, "provider_circuits",
                """
                SELECT provider, channel, state, failure_count, opened_at, retry_after,
                       updated_at, reason_codes_json
                FROM provider_circuits ORDER BY updated_at DESC LIMIT ?
                """, limit,
            ),
            paper_futures_orders=_query_if_table(
                connection, tables, "paper_futures_orders",
                "SELECT * FROM paper_futures_orders ORDER BY created_at DESC LIMIT ?", limit,
            ),
            paper_futures_fills=_query_if_table(
                connection, tables, "paper_futures_fills",
                "SELECT * FROM paper_futures_fills ORDER BY filled_at DESC LIMIT ?", limit,
            ),
            paper_funding_events=_query_if_table(
                connection, tables, "paper_funding_events",
                "SELECT * FROM paper_funding_events ORDER BY applied_at DESC LIMIT ?", limit,
            ),
            paper_order_events=_query_if_table(
                connection, tables, "paper_order_events",
                "SELECT * FROM paper_order_events ORDER BY event_at DESC LIMIT ?", limit,
            ),
            paper_stress_snapshots=_query_if_table(
                connection, tables, "paper_stress_snapshots",
                "SELECT * FROM paper_stress_snapshots ORDER BY captured_at DESC LIMIT ?", limit,
            ),
            model_artifacts=_query_if_table(
                connection, tables, "model_artifact_manifests",
                """
                SELECT artifact_id, model_id, version, direction, horizon, role, sha256,
                       rollback_artifact_id, active, created_at, metrics_json
                FROM model_artifact_manifests ORDER BY created_at DESC LIMIT ?
                """, limit,
            ),
            certification_runs=_query_if_table(
                connection, tables, "certification_runs",
                """
                SELECT certification_id, started_at, evaluated_at, required_hours,
                       elapsed_seconds, state, paper_simulation_enabled, report_json
                FROM certification_runs ORDER BY evaluated_at DESC LIMIT ?
                """, limit,
            ),
            decision_audit=_query_if_table(
                connection, tables, "signal_decisions",
                """
                WITH changes AS (
                    SELECT signal_id, instrument_id, horizon, generated_at, direction,
                           lag(direction) OVER (
                               PARTITION BY instrument_id, horizon ORDER BY generated_at, signal_id
                           ) AS previous_direction,
                           opportunity_score, risk_score, probability_state, model_version
                    FROM signal_decisions
                )
                SELECT * FROM changes
                WHERE previous_direction IS NULL OR direction <> previous_direction
                ORDER BY generated_at DESC LIMIT ?
                """, limit,
            ),
        )


def load_safety_status() -> dict[str, Any]:
    """Load static safety status from settings.yaml."""

    with SETTINGS_PATH.open(encoding="utf-8") as settings_file:
        settings = yaml.safe_load(settings_file)
    runtime = settings.get("runtime", {})
    llm_boundary = settings.get("llm_boundary", {})
    simulation = settings.get("simulation", {})
    return {
        "runtime_mode": runtime.get("mode"),
        "allowed_modes": ", ".join(runtime.get("allowed_modes", [])),
        "local_only": runtime.get("local_only"),
        "live_trading_implemented": runtime.get("live_trading_implemented"),
        "withdrawals_implemented": runtime.get("withdrawals_implemented"),
        "default_action": runtime.get("default_action"),
        "insufficient_data_action": runtime.get("insufficient_data_action"),
        "llm_direct_order_execution_allowed": llm_boundary.get("direct_order_execution_allowed"),
        "llm_secret_access_allowed": llm_boundary.get("secret_access_allowed"),
        "starting_capital_usd": simulation.get("starting_capital_usd"),
        "execution_target": simulation.get("execution_target"),
    }


def load_market_candles(
    database_path: str | Path,
    instrument_id: str,
    interval: str,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Load recent sufficient candles through a fixed, read-only query.

    This helper is intentionally separate from the single-writer repository. The
    API and Streamlit dashboard may read stored candles, but neither path can
    create a database, write market data, or select an arbitrary table/query.
    """

    if not instrument_id.strip():
        raise ValueError("instrument_id must not be empty")
    if interval not in MARKET_CANDLE_INTERVALS:
        raise ValueError(f"unsupported market interval: {interval}")
    if not 1 <= limit <= 2_000:
        raise ValueError("limit must be between 1 and 2000")

    path = Path(database_path)
    path = path if path.is_absolute() else SETTINGS_PATH.parents[1] / path
    if not path.exists():
        return []

    with duckdb.connect(database=str(path), read_only=True) as connection:
        tables = _list_tables(connection)
        if "market_candles" not in tables:
            return []
        cursor = connection.execute(
            """
            SELECT open_time_ms, open, high, low, close, base_volume,
                   quote_volume, source, received_at, quality
            FROM market_candles
            WHERE instrument_id = ?
              AND interval = ?
              AND quality = 'sufficient'
            ORDER BY open_time_ms DESC
            LIMIT ?
            """,
            [instrument_id, interval, limit],
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        return [
            _with_non_execution_flag(row)
            for row in reversed(rows)
        ]


def load_market_instruments(
    database_path: str | Path,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Load reviewed/local instrument identities through a bounded read query."""

    if not 1 <= limit <= 2_000:
        raise ValueError("limit must be between 1 and 2000")
    path = Path(database_path)
    path = path if path.is_absolute() else SETTINGS_PATH.parents[1] / path
    if not path.exists():
        return []

    with duckdb.connect(database=str(path), read_only=True) as connection:
        tables = _list_tables(connection)
        if "market_instruments" not in tables:
            return []
        cursor = connection.execute(
            """
            SELECT instrument_id, source, symbol, base_asset, quote_asset,
                   status, discovered_at, refreshed_at
            FROM market_instruments
            ORDER BY refreshed_at DESC, instrument_id
            LIMIT ?
            """,
            [limit],
        )
        columns = [column[0] for column in cursor.description]
        return [
            _with_non_execution_flag(dict(zip(columns, row, strict=True)))
            for row in cursor.fetchall()
        ]


def _list_tables(connection: duckdb.DuckDBPyConnection) -> set[str]:
    rows = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        """
    ).fetchall()
    return {row[0] for row in rows}


def _query_if_table(
    connection: duckdb.DuckDBPyConnection,
    tables: set[str],
    table_name: str,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    if table_name not in tables:
        return []
    cursor = connection.execute(query, [limit])
    columns = [column[0] for column in cursor.description]
    return [_with_non_execution_flag(dict(zip(columns, row, strict=True))) for row in cursor.fetchall()]


def _with_non_execution_flag(row: dict[str, Any]) -> dict[str, Any]:
    row.setdefault("can_execute_trades", False)
    return row
