"""Read-only DuckDB queries for the local Streamlit dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import yaml

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"
DEFAULT_LIMIT = 20


@dataclass(frozen=True)
class DashboardData:
    """All read-only dashboard sections fetched from local storage."""

    database_path: Path
    database_exists: bool
    tables: set[str]
    market_snapshots: list[dict[str, Any]]
    technical_vectors: list[dict[str, Any]]
    anti_rug_status: list[dict[str, Any]]
    risk_decisions: list[dict[str, Any]]
    simulated_orders: list[dict[str, Any]]
    simulated_fills: list[dict[str, Any]]
    audit_events: list[dict[str, Any]]
    safety_status: dict[str, Any]


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
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
