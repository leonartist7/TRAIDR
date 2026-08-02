"""Explicit DuckDB schema initialization for local research storage."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

import duckdb

SCHEMA_VERSION = 8
EXPECTED_TABLES = frozenset(
    {
        "agent_analyses",
        "audit_events",
        "cio_decisions",
        "evidence_snapshots",
        "macro_news_events",
        "lifecycle_events",
        "manual_portfolio_entries",
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
        "watchlist_entries",
        "watchlist_scan_results",
        "market_instruments",
        "market_events",
        "market_candles",
        "market_microstructure",
        "data_health",
        "ingestion_gaps",
        "feature_snapshots",
        "signal_decisions",
        "outcome_labels",
        "backtest_runs",
        "calibration_reports",
        "model_versions",
        "paper_futures_orders",
        "paper_futures_fills",
        "paper_futures_positions",
        "paper_funding_events",
        "paper_futures_portfolios",
        "service_heartbeats",
        "control_requests",
        "canonical_assets",
        "source_bindings",
        "evidence_bundles",
        "news_evidence",
        "onchain_evidence",
        "provider_circuits",
        "paper_order_events",
        "paper_stress_snapshots",
        "model_artifact_manifests",
        "certification_runs",
        "certification_faults",
        "market_scanner_scores",
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
    """
    CREATE TABLE IF NOT EXISTS watchlist_entries (
        pair_ref VARCHAR PRIMARY KEY,
        note VARCHAR NOT NULL,
        tags_json VARCHAR NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        active BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist_scan_results (
        scan_id VARCHAR PRIMARY KEY,
        pair_ref VARCHAR NOT NULL,
        scanned_at TIMESTAMP NOT NULL,
        status VARCHAR NOT NULL,
        radar_state VARCHAR NOT NULL,
        opportunity_score DOUBLE NOT NULL,
        risk_score DOUBLE NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lifecycle_events (
        event_id VARCHAR PRIMARY KEY,
        recorded_at TIMESTAMP NOT NULL,
        subject_id VARCHAR NOT NULL,
        event_type VARCHAR NOT NULL,
        from_state VARCHAR,
        to_state VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS manual_portfolio_entries (
        entry_id VARCHAR PRIMARY KEY,
        symbol VARCHAR NOT NULL,
        chain VARCHAR NOT NULL,
        pair_ref VARCHAR NOT NULL,
        entry_price DECIMAL(30, 12) NOT NULL,
        size_usd DECIMAL(18, 8) NOT NULL,
        thesis VARCHAR NOT NULL,
        stop_zone VARCHAR NOT NULL,
        take_profit_zone VARCHAR NOT NULL,
        conviction VARCHAR NOT NULL,
        risk_level VARCHAR NOT NULL,
        notes VARCHAR NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        active BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_instruments (
        instrument_id VARCHAR PRIMARY KEY,
        source VARCHAR NOT NULL,
        symbol VARCHAR NOT NULL,
        base_asset VARCHAR NOT NULL,
        quote_asset VARCHAR NOT NULL,
        status VARCHAR NOT NULL,
        discovered_at TIMESTAMP NOT NULL,
        refreshed_at TIMESTAMP NOT NULL,
        contract_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_events (
        event_id VARCHAR PRIMARY KEY,
        idempotency_key VARCHAR NOT NULL UNIQUE,
        data_mode VARCHAR NOT NULL,
        source VARCHAR NOT NULL,
        instrument_id VARCHAR NOT NULL,
        channel VARCHAR NOT NULL,
        event_at TIMESTAMP NOT NULL,
        received_at TIMESTAMP NOT NULL,
        sequence BIGINT,
        payload_version VARCHAR NOT NULL,
        schema_fingerprint VARCHAR NOT NULL,
        quality VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_candles (
        instrument_id VARCHAR NOT NULL,
        interval VARCHAR NOT NULL,
        open_time_ms BIGINT NOT NULL,
        open DECIMAL(30, 12) NOT NULL,
        high DECIMAL(30, 12) NOT NULL,
        low DECIMAL(30, 12) NOT NULL,
        close DECIMAL(30, 12) NOT NULL,
        base_volume DECIMAL(30, 12) NOT NULL,
        quote_volume DECIMAL(30, 12) NOT NULL,
        source VARCHAR NOT NULL,
        received_at TIMESTAMP NOT NULL,
        quality VARCHAR NOT NULL,
        PRIMARY KEY (instrument_id, interval, open_time_ms)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_microstructure (
        metric_id VARCHAR PRIMARY KEY,
        instrument_id VARCHAR NOT NULL,
        observed_at TIMESTAMP NOT NULL,
        bid_price DECIMAL(30, 12),
        ask_price DECIMAL(30, 12),
        spread_bps DOUBLE,
        depth_imbalance DOUBLE,
        trade_delta DOUBLE,
        mark_price DECIMAL(30, 12),
        index_price DECIMAL(30, 12),
        basis_bps DOUBLE,
        funding_rate DOUBLE,
        payload_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_health (
        source VARCHAR NOT NULL,
        instrument_id VARCHAR NOT NULL,
        channel VARCHAR NOT NULL,
        checked_at TIMESTAMP NOT NULL,
        status VARCHAR NOT NULL,
        last_event_at TIMESTAMP,
        lag_seconds DOUBLE,
        reconnect_count INTEGER NOT NULL,
        gap_count INTEGER NOT NULL,
        coverage DOUBLE NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        PRIMARY KEY (source, instrument_id, channel)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion_gaps (
        gap_id VARCHAR PRIMARY KEY,
        source VARCHAR NOT NULL,
        instrument_id VARCHAR NOT NULL,
        channel VARCHAR NOT NULL,
        detected_at TIMESTAMP NOT NULL,
        gap_start TIMESTAMP,
        gap_end TIMESTAMP,
        status VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_snapshots (
        feature_id VARCHAR PRIMARY KEY,
        instrument_id VARCHAR NOT NULL,
        horizon VARCHAR NOT NULL,
        observed_at TIMESTAMP NOT NULL,
        calculated_at TIMESTAMP NOT NULL,
        feature_version VARCHAR NOT NULL,
        regime VARCHAR NOT NULL,
        data_coverage DOUBLE NOT NULL,
        features_json VARCHAR NOT NULL,
        missing_features_json VARCHAR NOT NULL,
        quality_warnings_json VARCHAR NOT NULL,
        contradiction_flags_json VARCHAR NOT NULL,
        evidence_ids_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signal_decisions (
        signal_id VARCHAR PRIMARY KEY,
        idempotency_key VARCHAR NOT NULL UNIQUE,
        instrument_id VARCHAR NOT NULL,
        direction VARCHAR NOT NULL,
        horizon VARCHAR NOT NULL,
        setup_type VARCHAR NOT NULL,
        generated_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        opportunity_score DOUBLE NOT NULL,
        risk_score DOUBLE NOT NULL,
        data_coverage DOUBLE NOT NULL,
        probability_state VARCHAR NOT NULL,
        success_probability DOUBLE,
        calibration_sample_size INTEGER NOT NULL,
        model_version VARCHAR NOT NULL,
        decision_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outcome_labels (
        outcome_id VARCHAR PRIMARY KEY,
        signal_id VARCHAR NOT NULL,
        evaluated_at TIMESTAMP NOT NULL,
        target_before_stop BOOLEAN,
        net_return_pct DOUBLE NOT NULL,
        maximum_favorable_excursion_pct DOUBLE NOT NULL,
        maximum_adverse_excursion_pct DOUBLE NOT NULL,
        time_in_trade_seconds BIGINT NOT NULL,
        reason_codes_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id VARCHAR PRIMARY KEY,
        started_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP NOT NULL,
        strategy_version VARCHAR NOT NULL,
        data_start TIMESTAMP NOT NULL,
        data_end TIMESTAMP NOT NULL,
        outcome_count INTEGER NOT NULL,
        metrics_json VARCHAR NOT NULL,
        regime_metrics_json VARCHAR NOT NULL DEFAULT '{}',
        replay_hash VARCHAR NOT NULL DEFAULT '',
        no_lookahead_verified BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS calibration_reports (
        calibration_id VARCHAR PRIMARY KEY,
        direction VARCHAR NOT NULL,
        horizon VARCHAR NOT NULL,
        generated_at TIMESTAMP NOT NULL,
        sample_size INTEGER NOT NULL,
        brier_score DOUBLE NOT NULL,
        expected_calibration_error DOUBLE NOT NULL,
        method VARCHAR NOT NULL,
        eligible_for_display BOOLEAN NOT NULL,
        reason_codes_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_versions (
        model_id VARCHAR NOT NULL,
        version VARCHAR NOT NULL,
        role VARCHAR NOT NULL,
        feature_version VARCHAR NOT NULL,
        training_start TIMESTAMP NOT NULL,
        training_end TIMESTAMP NOT NULL,
        metrics_json VARCHAR NOT NULL,
        artifact_path VARCHAR NOT NULL,
        active BOOLEAN NOT NULL,
        PRIMARY KEY (model_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_futures_orders (
        order_id VARCHAR PRIMARY KEY,
        signal_id VARCHAR NOT NULL,
        instrument_id VARCHAR NOT NULL,
        direction VARCHAR NOT NULL,
        created_at TIMESTAMP NOT NULL,
        leverage DECIMAL(10, 4) NOT NULL,
        requested_notional_usd DECIMAL(18, 8) NOT NULL,
        requested_margin_usd DECIMAL(18, 8) NOT NULL,
        reference_price DECIMAL(30, 12) NOT NULL,
        status VARCHAR NOT NULL,
        idempotency_key VARCHAR NOT NULL UNIQUE,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_futures_fills (
        fill_id VARCHAR PRIMARY KEY,
        order_id VARCHAR NOT NULL,
        filled_at TIMESTAMP NOT NULL,
        quantity DECIMAL(30, 12) NOT NULL,
        fill_price DECIMAL(30, 12) NOT NULL,
        notional_usd DECIMAL(18, 8) NOT NULL,
        fee_usd DECIMAL(18, 8) NOT NULL,
        slippage_bps DECIMAL(12, 6) NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_futures_positions (
        position_id VARCHAR PRIMARY KEY,
        instrument_id VARCHAR NOT NULL,
        direction VARCHAR NOT NULL,
        opened_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        status VARCHAR NOT NULL,
        position_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_funding_events (
        funding_event_id VARCHAR PRIMARY KEY,
        position_id VARCHAR NOT NULL,
        applied_at TIMESTAMP NOT NULL,
        funding_rate DECIMAL(20, 12) NOT NULL,
        payment_usd DECIMAL(18, 8) NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_futures_portfolios (
        portfolio_snapshot_id VARCHAR PRIMARY KEY,
        captured_at TIMESTAMP NOT NULL,
        equity_usd DECIMAL(18, 8) NOT NULL,
        cash_usd DECIMAL(18, 8) NOT NULL,
        used_margin_usd DECIMAL(18, 8) NOT NULL,
        daily_pnl_usd DECIMAL(18, 8) NOT NULL,
        halted BOOLEAN NOT NULL,
        snapshot_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS service_heartbeats (
        service_name VARCHAR PRIMARY KEY,
        process_id INTEGER NOT NULL,
        started_at TIMESTAMP NOT NULL,
        heartbeat_at TIMESTAMP NOT NULL,
        status VARCHAR NOT NULL,
        data_mode VARCHAR NOT NULL,
        details_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS control_requests (
        request_id VARCHAR PRIMARY KEY,
        idempotency_key VARCHAR NOT NULL UNIQUE,
        requested_at TIMESTAMP NOT NULL,
        action VARCHAR NOT NULL,
        status VARCHAR NOT NULL,
        payload_json VARCHAR NOT NULL,
        completed_at TIMESTAMP,
        result_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_assets (
        canonical_asset_id VARCHAR PRIMARY KEY,
        symbol VARCHAR NOT NULL,
        name VARCHAR NOT NULL,
        aliases_json VARCHAR NOT NULL,
        review_state VARCHAR NOT NULL,
        reviewed_at TIMESTAMP NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_bindings (
        binding_id VARCHAR PRIMARY KEY,
        canonical_asset_id VARCHAR NOT NULL,
        source VARCHAR NOT NULL,
        binding_kind VARCHAR NOT NULL,
        source_identifier VARCHAR NOT NULL,
        chain_id VARCHAR,
        contract_address VARCHAR,
        review_state VARCHAR NOT NULL,
        reviewed_at TIMESTAMP NOT NULL,
        provenance VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE,
        UNIQUE(source, binding_kind, source_identifier, chain_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_bundles (
        bundle_id VARCHAR PRIMARY KEY,
        instrument_id VARCHAR NOT NULL,
        canonical_asset_id VARCHAR,
        observed_at TIMESTAMP NOT NULL,
        generated_at TIMESTAMP NOT NULL,
        feature_version VARCHAR NOT NULL,
        data_coverage DOUBLE NOT NULL,
        hard_vetoes_json VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        bundle_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_scanner_scores (
        score_id VARCHAR PRIMARY KEY,
        instrument_id VARCHAR NOT NULL,
        observed_at TIMESTAMP NOT NULL,
        recorded_at TIMESTAMP NOT NULL,
        status VARCHAR NOT NULL,
        direction VARCHAR NOT NULL,
        score DOUBLE,
        long_score DOUBLE,
        short_score DOUBLE,
        risk_score DOUBLE,
        conflicts_json VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        factor_breakdown_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_evidence (
        evidence_id VARCHAR PRIMARY KEY,
        canonical_asset_id VARCHAR,
        source VARCHAR NOT NULL,
        headline VARCHAR NOT NULL,
        normalized_headline VARCHAR NOT NULL,
        url VARCHAR NOT NULL,
        published_at TIMESTAMP NOT NULL,
        observed_at TIMESTAMP NOT NULL,
        reliability DOUBLE NOT NULL,
        relevance DOUBLE NOT NULL,
        age_weight DOUBLE NOT NULL,
        mapping_state VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        evidence_json VARCHAR NOT NULL,
        UNIQUE(url),
        UNIQUE(source, normalized_headline)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS onchain_evidence (
        evidence_id VARCHAR PRIMARY KEY,
        canonical_asset_id VARCHAR NOT NULL,
        source VARCHAR NOT NULL,
        chain_id VARCHAR NOT NULL,
        contract_address VARCHAR NOT NULL,
        observed_at TIMESTAMP NOT NULL,
        coverage DOUBLE NOT NULL,
        hard_vetoes_json VARCHAR NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        evidence_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS provider_circuits (
        provider VARCHAR NOT NULL,
        channel VARCHAR NOT NULL,
        state VARCHAR NOT NULL,
        failure_count INTEGER NOT NULL,
        opened_at TIMESTAMP,
        retry_after TIMESTAMP,
        updated_at TIMESTAMP NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        PRIMARY KEY(provider, channel)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_order_events (
        event_id VARCHAR PRIMARY KEY,
        order_id VARCHAR NOT NULL,
        position_id VARCHAR,
        event_at TIMESTAMP NOT NULL,
        event_type VARCHAR NOT NULL,
        idempotency_key VARCHAR NOT NULL UNIQUE,
        reason_codes_json VARCHAR NOT NULL,
        event_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_stress_snapshots (
        stress_id VARCHAR PRIMARY KEY,
        captured_at TIMESTAMP NOT NULL,
        portfolio_equity_usd DECIMAL(18, 8) NOT NULL,
        stressed_loss_usd DECIMAL(18, 8) NOT NULL,
        maximum_correlation DOUBLE NOT NULL,
        concentration_fraction DOUBLE NOT NULL,
        approved BOOLEAN NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        snapshot_json VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_artifact_manifests (
        artifact_id VARCHAR PRIMARY KEY,
        model_id VARCHAR NOT NULL,
        version VARCHAR NOT NULL,
        direction VARCHAR NOT NULL,
        horizon VARCHAR NOT NULL,
        role VARCHAR NOT NULL,
        training_start TIMESTAMP NOT NULL,
        training_end TIMESTAMP NOT NULL,
        sha256 VARCHAR NOT NULL,
        artifact_path VARCHAR NOT NULL,
        rollback_artifact_id VARCHAR,
        active BOOLEAN NOT NULL,
        created_at TIMESTAMP NOT NULL,
        metrics_json VARCHAR NOT NULL,
        manifest_json VARCHAR NOT NULL,
        UNIQUE(model_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS certification_runs (
        certification_id VARCHAR PRIMARY KEY,
        started_at TIMESTAMP NOT NULL,
        evaluated_at TIMESTAMP NOT NULL,
        required_hours INTEGER NOT NULL,
        elapsed_seconds BIGINT NOT NULL,
        state VARCHAR NOT NULL,
        paper_simulation_enabled BOOLEAN NOT NULL,
        report_json VARCHAR NOT NULL,
        can_execute_trades BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS certification_faults (
        fault_id VARCHAR PRIMARY KEY,
        certification_id VARCHAR NOT NULL,
        injected_at TIMESTAMP NOT NULL,
        fault_type VARCHAR NOT NULL,
        recovered BOOLEAN NOT NULL,
        reason_codes_json VARCHAR NOT NULL,
        details_json VARCHAR NOT NULL
    )
    """,
)

_ADDITIVE_DDL: tuple[str, ...] = (
    "ALTER TABLE ingestion_gaps ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR",
    "ALTER TABLE ingestion_gaps ADD COLUMN IF NOT EXISTS interval VARCHAR",
    "ALTER TABLE ingestion_gaps ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0",
    "ALTER TABLE ingestion_gaps ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
    "ALTER TABLE paper_funding_events ADD COLUMN IF NOT EXISTS funding_time TIMESTAMP",
    "ALTER TABLE paper_funding_events ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR",
    "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS regime_metrics_json VARCHAR DEFAULT '{}'",
    "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS replay_hash VARCHAR DEFAULT ''",
    "CREATE UNIQUE INDEX IF NOT EXISTS ingestion_gaps_idempotency_idx ON ingestion_gaps(idempotency_key)",
    "CREATE UNIQUE INDEX IF NOT EXISTS paper_funding_idempotency_idx ON paper_funding_events(idempotency_key)",
)


class SchemaInitializationError(RuntimeError):
    """Raised when local storage schema setup cannot be completed."""


def initialize_schema(connection: duckdb.DuckDBPyConnection) -> None:
    """Create the local storage schema and record the current schema version."""

    try:
        connection.begin()
        _execute_all(connection, _DDL)
        _execute_all(connection, _ADDITIVE_DDL)
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
