"""Explicit DuckDB schema initialization for local research storage."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

import duckdb

SCHEMA_VERSION = 2
EXPECTED_TABLES = frozenset(
    {
        "agent_analyses",
        "audit_events",
        "cio_decisions",
        "evidence_snapshots",
        "macro_news_events",
        "notification_alerts",
        "opportunity_radar_states",
        "portfolio_snapshots",
        "research_reports",
        "research_intents",
        "risk_decisions",
        "scheduler_runs",
        "schema_migrations",
        "simulated_fills",
        "simulated_orders",
        "technical_vectors",
    }
)

_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_snapshots (
        snapshot_id VARCHAR PRIMARY KEY,
        source_name VARCHAR NOT NULL,
        observed_at TIMESTAMP NOT NULL,
        collected_at TIMESTAMP NOT NULL,
        quality_status VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL,
        provenance_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS technical_vectors (
        vector_id VARCHAR PRIMARY KEY,
        snapshot_id VARCHAR,
        created_at TIMESTAMP NOT NULL,
        feature_status VARCHAR NOT NULL,
        features_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_intents (
        intent_id VARCHAR PRIMARY KEY,
        created_at TIMESTAMP NOT NULL,
        intent VARCHAR NOT NULL,
        output_status VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_toon VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_decisions (
        decision_id VARCHAR PRIMARY KEY,
        intent_id VARCHAR,
        decided_at TIMESTAMP NOT NULL,
        decision VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        details_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS simulated_orders (
        order_id VARCHAR PRIMARY KEY,
        risk_decision_id VARCHAR NOT NULL,
        created_at TIMESTAMP NOT NULL,
        side VARCHAR NOT NULL,
        pair_id VARCHAR NOT NULL,
        notional_usd DECIMAL(18, 8) NOT NULL,
        order_status VARCHAR NOT NULL,
        metadata_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS simulated_fills (
        fill_id VARCHAR PRIMARY KEY,
        order_id VARCHAR NOT NULL,
        filled_at TIMESTAMP NOT NULL,
        quantity DECIMAL(30, 12) NOT NULL,
        price_usd DECIMAL(30, 12) NOT NULL,
        notional_usd DECIMAL(18, 8) NOT NULL,
        metadata_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        portfolio_snapshot_id VARCHAR PRIMARY KEY,
        captured_at TIMESTAMP NOT NULL,
        cash_usd DECIMAL(18, 8) NOT NULL,
        exposure_usd DECIMAL(18, 8) NOT NULL,
        holdings_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        event_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        event_type VARCHAR NOT NULL,
        severity VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_analyses (
        analysis_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        agent_name VARCHAR NOT NULL,
        subject_id VARCHAR NOT NULL,
        status VARCHAR NOT NULL,
        confidence DOUBLE NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cio_decisions (
        decision_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        subject_id VARCHAR NOT NULL,
        recommendation VARCHAR NOT NULL,
        confidence DOUBLE NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS macro_news_events (
        event_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        event_type VARCHAR NOT NULL,
        subject_id VARCHAR NOT NULL,
        classification VARCHAR NOT NULL,
        confidence DOUBLE NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS opportunity_radar_states (
        radar_state_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        subject_id VARCHAR NOT NULL,
        state VARCHAR NOT NULL,
        rank INTEGER NOT NULL,
        opportunity_score DOUBLE NOT NULL,
        risk_score DOUBLE NOT NULL,
        confidence DOUBLE NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_alerts (
        alert_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        subject_id VARCHAR NOT NULL,
        channel VARCHAR NOT NULL,
        severity VARCHAR NOT NULL,
        fingerprint VARCHAR NOT NULL,
        status VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scheduler_runs (
        run_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        task_name VARCHAR NOT NULL,
        due_at TIMESTAMP NOT NULL,
        status VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_reports (
        report_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        report_type VARCHAR NOT NULL,
        status VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
)


class SchemaInitializationError(RuntimeError):
    """Raised when local storage schema setup cannot be completed."""


def initialize_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """Create the local storage schema and record the current schema version."""

    try:
        connection.begin()
        _execute_all(connection, _DDL)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, applied_at)
            SELECT ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM schema_migrations WHERE version = ?
            )
            """,
            [SCHEMA_VERSION, datetime.now(timezone.utc), SCHEMA_VERSION],
        )
        connection.commit()
    except Exception as exc:  # pragma: no cover - engine-specific error families vary
        connection.rollback()
        raise SchemaInitializationError("failed to initialize DuckDB schema") from exc


def list_tables(connection: duckdb.DuckDBPyConnection) -> set[str]:
    """Return tables in the main DuckDB schema."""

    rows = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        """
    ).fetchall()
    return {row[0] for row in rows}


def _execute_all(
    connection: duckdb.DuckDBPyConnection,
    statements: Iterable[str],
) -> None:
    for statement in statements:
        connection.execute(statement)
