"""Single-writer repositories for normalized live research and paper futures."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

import duckdb

from data_pipeline.bitunix_models import BitunixCandle, BitunixTradingPair
from execution.paper_futures import (
    PaperFuturesFill,
    PaperFuturesOrder,
    PaperPortfolioSnapshot,
    PaperPosition,
)
from scoring.live_scanner import ScannerScore
from intelligence.production_models import (
    CanonicalAssetIdentity,
    CertificationReport,
    DataHealth,
    EvidenceBundle,
    FeatureSnapshot,
    IngestionGap,
    MarketEvent,
    ModelArtifactManifest,
    OutcomeLabel,
    ProviderCircuitState,
    RiskAssessment,
    SignalDecision,
    SourceBinding,
)
from utils.toon import assert_safe_payload


class MarketRepository:
    """Persist idempotent normalized records through the service-owned connection."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def upsert_instrument(self, pair: BitunixTradingPair, *, now: datetime | None = None) -> str:
        refreshed = now or datetime.now(tz=UTC)
        instrument_id = f"bitunix:{pair.symbol}"
        self.connection.execute(
            """
            INSERT INTO market_instruments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (instrument_id) DO UPDATE SET
                status = excluded.status,
                refreshed_at = excluded.refreshed_at,
                contract_json = excluded.contract_json,
                can_execute_trades = FALSE
            """,
            [
                instrument_id,
                "bitunix",
                pair.symbol,
                pair.base,
                pair.quote,
                pair.symbol_status,
                refreshed,
                refreshed,
                _safe_json(pair.model_dump(mode="json")),
            ],
        )
        return instrument_id

    def upsert_canonical_identity(self, identity: CanonicalAssetIdentity) -> None:
        self.connection.execute(
            """
            INSERT INTO canonical_assets VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (canonical_asset_id) DO UPDATE SET
                symbol = excluded.symbol,
                name = excluded.name,
                aliases_json = excluded.aliases_json,
                review_state = excluded.review_state,
                reviewed_at = excluded.reviewed_at,
                reason_codes_json = excluded.reason_codes_json,
                can_execute_trades = FALSE
            """,
            [
                identity.canonical_asset_id,
                identity.symbol,
                identity.name,
                _safe_json(identity.aliases),
                identity.review_state.value,
                identity.reviewed_at,
                _safe_json(identity.reason_codes),
            ],
        )

    def upsert_source_binding(self, binding: SourceBinding) -> None:
        self.connection.execute(
            """
            INSERT INTO source_bindings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (binding_id) DO UPDATE SET
                canonical_asset_id = excluded.canonical_asset_id,
                review_state = excluded.review_state,
                reviewed_at = excluded.reviewed_at,
                provenance = excluded.provenance,
                reason_codes_json = excluded.reason_codes_json,
                can_execute_trades = FALSE
            """,
            [
                binding.binding_id,
                binding.canonical_asset_id,
                binding.source,
                binding.binding_kind,
                binding.source_identifier,
                binding.chain_id,
                binding.contract_address,
                binding.review_state.value,
                binding.reviewed_at,
                binding.provenance,
                _safe_json(binding.reason_codes),
            ],
        )

    def seed_reviewed_identities(self) -> None:
        from data_pipeline.asset_identity import reviewed_seed_bindings, reviewed_seed_identities

        for identity in reviewed_seed_identities():
            self.upsert_canonical_identity(identity)
        for binding in reviewed_seed_bindings():
            self.upsert_source_binding(binding)

    def record_market_event(self, event: MarketEvent) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO market_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING event_id
            """,
            [
                event.event_id,
                event.idempotency_key,
                event.data_mode.value,
                event.source,
                event.instrument_id,
                event.channel.value,
                event.event_at,
                event.received_at,
                event.sequence,
                event.payload_version,
                event.schema_fingerprint,
                event.quality.value,
                _safe_json(event.reason_codes),
                _safe_json(event.payload),
            ],
        )
        return cursor.fetchone() is not None

    def upsert_candles(
        self,
        instrument_id: str,
        interval: str,
        candles: Sequence[BitunixCandle],
        *,
        received_at: datetime | None = None,
    ) -> int:
        received = received_at or datetime.now(tz=UTC)
        written = 0
        for candle in candles:
            cursor = self.connection.execute(
                """
                INSERT INTO market_candles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (instrument_id, interval, open_time_ms) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    base_volume = excluded.base_volume,
                    quote_volume = excluded.quote_volume,
                    received_at = excluded.received_at,
                    quality = excluded.quality
                RETURNING open_time_ms
                """,
                [
                    instrument_id,
                    interval,
                    candle.time_ms,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.base_volume,
                    candle.quote_volume,
                    "bitunix",
                    received,
                    "sufficient",
                ],
            )
            written += int(cursor.fetchone() is not None)
        return written

    def load_recent_candles(
        self,
        instrument_id: str,
        interval: str,
        *,
        limit: int = 2000,
    ) -> tuple[BitunixCandle, ...]:
        rows = self.connection.execute(
            """
            SELECT open_time_ms, open, high, low, close, quote_volume, base_volume
            FROM market_candles
            WHERE instrument_id = ? AND interval = ? AND quality = 'sufficient'
            ORDER BY open_time_ms DESC
            LIMIT ?
            """,
            [instrument_id, interval, limit],
        ).fetchall()
        symbol = instrument_id.split(":", 1)[-1]
        return tuple(
            BitunixCandle(
                symbol=symbol,
                interval=interval,
                time_ms=row[0],
                open=row[1],
                high=row[2],
                low=row[3],
                close=row[4],
                quote_volume=row[5],
                base_volume=row[6],
            )
            for row in reversed(rows)
        )

    def record_microstructure(
        self,
        *,
        metric_id: str,
        instrument_id: str,
        observed_at: datetime,
        bid_price: Any = None,
        ask_price: Any = None,
        spread_bps: float | None = None,
        depth_imbalance: float | None = None,
        trade_delta: float | None = None,
        mark_price: Any = None,
        index_price: Any = None,
        basis_bps: float | None = None,
        funding_rate: float | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO market_microstructure VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (metric_id) DO NOTHING
            RETURNING metric_id
            """,
            [metric_id, instrument_id, observed_at, bid_price, ask_price, spread_bps,
             depth_imbalance, trade_delta, mark_price, index_price, basis_bps, funding_rate,
             _safe_json(payload or {})],
        )
        return cursor.fetchone() is not None

    def upsert_health(self, health: DataHealth) -> None:
        self.connection.execute(
            """
            INSERT INTO data_health VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source, instrument_id, channel) DO UPDATE SET
                checked_at = excluded.checked_at,
                status = excluded.status,
                last_event_at = excluded.last_event_at,
                lag_seconds = excluded.lag_seconds,
                reconnect_count = excluded.reconnect_count,
                gap_count = excluded.gap_count,
                coverage = excluded.coverage,
                reason_codes_json = excluded.reason_codes_json
            """,
            [
                health.source,
                health.instrument_id,
                health.channel.value,
                health.checked_at,
                health.status,
                health.last_event_at,
                health.lag_seconds,
                health.reconnect_count,
                health.gap_count,
                health.coverage,
                _safe_json(health.reason_codes),
            ],
        )

    def upsert_ingestion_gap(self, gap: IngestionGap) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO ingestion_gaps (
                gap_id, source, instrument_id, channel, detected_at, gap_start, gap_end,
                status, reason_codes_json, idempotency_key, interval, attempts, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (idempotency_key) DO UPDATE SET
                status = excluded.status,
                attempts = excluded.attempts,
                updated_at = excluded.updated_at,
                reason_codes_json = excluded.reason_codes_json
            RETURNING gap_id
            """,
            [
                gap.gap_id,
                gap.source,
                gap.instrument_id,
                gap.channel.value,
                gap.detected_at,
                gap.gap_start,
                gap.gap_end,
                gap.status.value,
                _safe_json(gap.reason_codes),
                gap.idempotency_key,
                gap.interval,
                gap.attempts,
                gap.updated_at,
            ],
        )
        return cursor.fetchone() is not None

    def has_unresolved_gap(self, instrument_id: str) -> bool:
        row = self.connection.execute(
            """
            SELECT count(*) FROM ingestion_gaps
            WHERE instrument_id = ? AND status IN ('DETECTED', 'BACKFILLING', 'UNRESOLVED')
            """,
            [instrument_id],
        ).fetchone()
        return bool(row and row[0])

    def upsert_provider_circuit(self, circuit: ProviderCircuitState) -> None:
        self.connection.execute(
            """
            INSERT INTO provider_circuits VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (provider, channel) DO UPDATE SET
                state = excluded.state,
                failure_count = excluded.failure_count,
                opened_at = excluded.opened_at,
                retry_after = excluded.retry_after,
                updated_at = excluded.updated_at,
                reason_codes_json = excluded.reason_codes_json
            """,
            [
                circuit.provider,
                circuit.channel,
                circuit.state.value,
                circuit.failure_count,
                circuit.opened_at,
                circuit.retry_after,
                circuit.updated_at,
                _safe_json(circuit.reason_codes),
            ],
        )

    def record_evidence_bundle(self, bundle: EvidenceBundle) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO evidence_bundles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (bundle_id) DO NOTHING
            RETURNING bundle_id
            """,
            [
                bundle.bundle_id,
                bundle.instrument_id,
                bundle.canonical_asset_id,
                bundle.observed_at,
                bundle.generated_at,
                bundle.feature_version,
                bundle.data_coverage,
                _safe_json(bundle.hard_vetoes),
                _safe_json(bundle.reason_codes),
                _safe_json(bundle.model_dump(mode="json")),
            ],
        )
        return cursor.fetchone() is not None

    def record_scanner_score(self, score: ScannerScore) -> bool:
        """Persist a deterministic factor breakdown for the read-only dashboard."""

        observed_at = score.observed_at or datetime.now(tz=UTC)
        score_id = f"scanner:{score.instrument_id}:{observed_at.isoformat()}"
        cursor = self.connection.execute(
            """
            INSERT INTO market_scanner_scores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (score_id) DO UPDATE SET
                recorded_at = excluded.recorded_at,
                status = excluded.status,
                direction = excluded.direction,
                score = excluded.score,
                long_score = excluded.long_score,
                short_score = excluded.short_score,
                risk_score = excluded.risk_score,
                conflicts_json = excluded.conflicts_json,
                reason_codes_json = excluded.reason_codes_json,
                factor_breakdown_json = excluded.factor_breakdown_json
            RETURNING score_id
            """,
            [
                score_id,
                score.instrument_id,
                observed_at,
                datetime.now(tz=UTC),
                score.status,
                score.direction.value,
                score.score,
                score.long_score,
                score.short_score,
                score.risk_score,
                _safe_json(score.conflicts),
                _safe_json(score.reason_codes),
                _safe_json(score.factor_breakdown()),
            ],
        )
        return cursor.fetchone() is not None

    def record_news_evidence(self, evidence: Mapping[str, Any]) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO news_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            RETURNING evidence_id
            """,
            [
                evidence["evidence_id"], evidence.get("canonical_asset_id"), evidence["source"],
                evidence["headline"], evidence["normalized_headline"], evidence["url"],
                evidence["published_at"], evidence["observed_at"], evidence["reliability"],
                evidence["relevance"], evidence["age_weight"], evidence["mapping_state"],
                _safe_json(evidence["reason_codes"]), _safe_json(evidence),
            ],
        )
        return cursor.fetchone() is not None

    def record_onchain_evidence(self, evidence: Mapping[str, Any]) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO onchain_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (evidence_id) DO NOTHING
            RETURNING evidence_id
            """,
            [
                evidence["evidence_id"], evidence["canonical_asset_id"], evidence["source"],
                evidence["chain_id"], evidence["contract_address"], evidence["observed_at"],
                evidence["coverage"], _safe_json(evidence.get("hard_vetoes", ())),
                _safe_json(evidence.get("reason_codes", ())), _safe_json(evidence),
            ],
        )
        return cursor.fetchone() is not None

    def record_feature(self, snapshot: FeatureSnapshot) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO feature_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (feature_id) DO NOTHING
            RETURNING feature_id
            """,
            [
                snapshot.feature_id,
                snapshot.instrument_id,
                snapshot.horizon,
                snapshot.observed_at,
                snapshot.calculated_at,
                snapshot.feature_version,
                snapshot.regime,
                snapshot.data_coverage,
                _safe_json(snapshot.features),
                _safe_json(snapshot.missing_features),
                _safe_json(snapshot.quality_warnings),
                _safe_json(snapshot.contradiction_flags),
                _safe_json(snapshot.evidence_ids),
            ],
        )
        return cursor.fetchone() is not None

    def record_signal(self, signal: SignalDecision) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO signal_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING signal_id
            """,
            [
                signal.signal_id,
                signal.idempotency_key,
                signal.instrument_id,
                signal.direction.value,
                signal.horizon,
                signal.setup_type,
                signal.generated_at,
                signal.expires_at,
                signal.opportunity_score,
                signal.risk_score,
                signal.data_coverage,
                signal.probability_state.value,
                signal.success_probability,
                signal.calibration_sample_size,
                signal.model_version,
                _safe_json(signal.model_dump(mode="json")),
            ],
        )
        return cursor.fetchone() is not None

    def record_risk_assessment(self, assessment: RiskAssessment) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO risk_decisions VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (decision_id) DO NOTHING
            RETURNING decision_id
            """,
            [
                assessment.assessment_id,
                assessment.signal_id,
                assessment.decided_at,
                assessment.outcome,
                _safe_json(assessment.reason_codes),
                _safe_json(assessment.model_dump(mode="json")),
            ],
        )
        return cursor.fetchone() is not None

    def record_outcome(self, outcome: OutcomeLabel) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO outcome_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (outcome_id) DO NOTHING
            RETURNING outcome_id
            """,
            [
                outcome.outcome_id,
                outcome.signal_id,
                outcome.evaluated_at,
                outcome.target_before_stop,
                outcome.net_return_pct,
                outcome.maximum_favorable_excursion_pct,
                outcome.maximum_adverse_excursion_pct,
                outcome.time_in_trade_seconds,
                _safe_json(outcome.reason_codes),
            ],
        )
        return cursor.fetchone() is not None

    def record_model_artifact(self, manifest: ModelArtifactManifest) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO model_artifact_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (artifact_id) DO NOTHING
            RETURNING artifact_id
            """,
            [
                manifest.artifact_id, manifest.model_id, manifest.version, manifest.direction.value,
                manifest.horizon, manifest.role, manifest.training_start, manifest.training_end,
                manifest.sha256, manifest.artifact_path, manifest.rollback_artifact_id,
                manifest.active, manifest.created_at, _safe_json(manifest.metrics),
                _safe_json(manifest.model_dump(mode="json")),
            ],
        )
        return cursor.fetchone() is not None

    def record_calibration_report(self, report: Any) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO calibration_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (calibration_id) DO NOTHING
            RETURNING calibration_id
            """,
            [
                report.calibration_id, report.direction.value, report.horizon, report.generated_at,
                report.sample_size, report.brier_score, report.expected_calibration_error,
                report.method, report.eligible_for_display, _safe_json(report.reason_codes),
            ],
        )
        return cursor.fetchone() is not None

    def record_certification(self, report: CertificationReport) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO certification_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (certification_id) DO UPDATE SET
                evaluated_at = excluded.evaluated_at,
                elapsed_seconds = excluded.elapsed_seconds,
                state = excluded.state,
                paper_simulation_enabled = FALSE,
                report_json = excluded.report_json,
                can_execute_trades = FALSE
            RETURNING certification_id
            """,
            [
                report.certification_id, report.started_at, report.evaluated_at,
                report.required_hours, report.elapsed_seconds, report.state,
                report.paper_simulation_enabled, _safe_json(report.model_dump(mode="json")),
            ],
        )
        return cursor.fetchone() is not None

    def record_paper_order_event(
        self,
        *,
        event_id: str,
        order_id: str,
        position_id: str | None,
        event_at: datetime,
        event_type: str,
        idempotency_key: str,
        reason_codes: tuple[str, ...],
        payload: Mapping[str, Any],
    ) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO paper_order_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, FALSE)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING event_id
            """,
            [event_id, order_id, position_id, event_at, event_type, idempotency_key,
             _safe_json(reason_codes), _safe_json(payload)],
        )
        return cursor.fetchone() is not None

    def record_paper_funding(
        self,
        *,
        funding_event_id: str,
        position_id: str,
        funding_time: datetime,
        funding_rate: Any,
        payment_usd: Any,
        idempotency_key: str,
    ) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO paper_funding_events (
                funding_event_id, position_id, applied_at, funding_rate, payment_usd,
                funding_time, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING funding_event_id
            """,
            [funding_event_id, position_id, datetime.now(tz=UTC), funding_rate, payment_usd,
             funding_time, idempotency_key],
        )
        return cursor.fetchone() is not None

    def record_paper_execution(
        self,
        order: PaperFuturesOrder,
        fill: PaperFuturesFill,
        position: PaperPosition,
    ) -> None:
        self.connection.begin()
        try:
            self.connection.execute(
                "INSERT INTO paper_futures_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE)",
                [
                    order.order_id,
                    order.signal_id,
                    order.instrument_id,
                    order.direction.value,
                    order.created_at,
                    order.leverage,
                    order.requested_notional_usd,
                    order.requested_margin_usd,
                    order.reference_price,
                    order.status,
                    order.idempotency_key,
                ],
            )
            self.connection.execute(
                "INSERT INTO paper_futures_fills VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    fill.fill_id,
                    fill.order_id,
                    fill.filled_at,
                    fill.quantity,
                    fill.fill_price,
                    fill.notional_usd,
                    fill.fee_usd,
                    fill.slippage_bps,
                ],
            )
            self.upsert_paper_position(position)
            self.record_paper_order_event(
                event_id=f"event:{fill.fill_id}",
                order_id=order.order_id,
                position_id=position.position_id,
                event_at=fill.filled_at,
                event_type=order.status,
                idempotency_key=f"{order.idempotency_key}:{order.status.lower()}",
                reason_codes=(
                    "PAPER_PARTIAL_FILL" if order.status == "PARTIAL" else "PAPER_FILLED",
                    "NO_EXECUTION_ACTION",
                ),
                payload={"order": _dataclass_json(order), "fill": _dataclass_json(fill)},
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def upsert_paper_position(self, position: PaperPosition) -> None:
        self.connection.execute(
            """
            INSERT INTO paper_futures_positions VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (position_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                status = excluded.status,
                position_json = excluded.position_json
            """,
            [
                position.position_id,
                position.instrument_id,
                position.direction.value,
                position.opened_at,
                position.updated_at,
                position.status.value,
                _safe_json(_dataclass_json(position)),
            ],
        )

    def record_portfolio(self, snapshot: PaperPortfolioSnapshot) -> str:
        snapshot_id = f"pf-portfolio-{uuid4().hex}"
        self.connection.execute(
            "INSERT INTO paper_futures_portfolios VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                snapshot_id,
                snapshot.captured_at,
                snapshot.equity_usd,
                snapshot.cash_usd,
                snapshot.used_margin_usd,
                snapshot.daily_pnl_usd,
                snapshot.halted,
                _safe_json(_dataclass_json(snapshot)),
            ],
        )
        return snapshot_id

    def record_stress_snapshot(self, snapshot: Any) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO paper_stress_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (stress_id) DO NOTHING
            RETURNING stress_id
            """,
            [
                snapshot.stress_id, snapshot.captured_at, snapshot.portfolio_equity_usd,
                snapshot.stressed_loss_usd, snapshot.maximum_correlation,
                snapshot.concentration_fraction, snapshot.approved,
                _safe_json(snapshot.reason_codes), _safe_json(_dataclass_json(snapshot)),
            ],
        )
        return cursor.fetchone() is not None

    def load_paper_recovery(self) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
        """Load the most recent portfolio snapshot and processed paper signal keys."""

        row = self.connection.execute(
            """
            SELECT snapshot_json
            FROM paper_futures_portfolios
            ORDER BY captured_at DESC
            LIMIT 1
            """
        ).fetchone()
        payload: dict[str, Any] | None = None
        if row and row[0]:
            parsed = json.loads(str(row[0]))
            if isinstance(parsed, dict):
                payload = parsed
                payload["processed_funding_keys"] = [
                    str(item[0])
                    for item in self.connection.execute(
                        "SELECT idempotency_key FROM paper_funding_events WHERE idempotency_key IS NOT NULL"
                    ).fetchall()
                    if item and item[0]
                ]
        keys = tuple(
            str(item[0])
            for item in self.connection.execute(
                "SELECT idempotency_key FROM paper_futures_orders ORDER BY created_at"
            ).fetchall()
            if item and item[0]
        )
        return payload, keys

    def apply_retention(self, *, now: datetime | None = None) -> None:
        """Enforce diagnostic-frame and high-frequency research retention windows."""

        reference = now or datetime.now(tz=UTC)
        self.connection.execute(
            "DELETE FROM market_events WHERE received_at < ? - INTERVAL '24 hours'",
            [reference],
        )
        self.connection.execute(
            "DELETE FROM market_microstructure WHERE observed_at < ? - INTERVAL '90 days'",
            [reference],
        )

    def heartbeat(
        self,
        *,
        service_name: str,
        started_at: datetime,
        status: str,
        data_mode: str,
        details: Mapping[str, Any],
        now: datetime | None = None,
    ) -> None:
        heartbeat_at = now or datetime.now(tz=UTC)
        self.connection.execute(
            """
            INSERT INTO service_heartbeats VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (service_name) DO UPDATE SET
                process_id = excluded.process_id,
                heartbeat_at = excluded.heartbeat_at,
                status = excluded.status,
                data_mode = excluded.data_mode,
                details_json = excluded.details_json
            """,
            [service_name, os.getpid(), started_at, heartbeat_at, status, data_mode, _safe_json(details)],
        )

    def record_control_request(
        self,
        *,
        request_id: str,
        idempotency_key: str,
        action: str,
        payload: Mapping[str, Any],
        requested_at: datetime | None = None,
    ) -> bool:
        cursor = self.connection.execute(
            """
            INSERT INTO control_requests VALUES (?, ?, ?, ?, 'PENDING', ?, NULL, '{}')
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING request_id
            """,
            [request_id, idempotency_key, requested_at or datetime.now(tz=UTC), action, _safe_json(payload)],
        )
        return cursor.fetchone() is not None

    def complete_control_request(
        self,
        request_id: str,
        *,
        status: str,
        result: Mapping[str, Any],
        completed_at: datetime | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE control_requests
            SET status = ?, completed_at = ?, result_json = ?
            WHERE request_id = ?
            """,
            [status, completed_at or datetime.now(tz=UTC), _safe_json(result), request_id],
        )


def _safe_json(value: Any) -> str:
    normalized = _normalize(value)
    assert_safe_payload(normalized)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        enum_value = value.value
    except AttributeError:
        enum_value = None
    if isinstance(enum_value, str):
        return enum_value
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if hasattr(value, "as_tuple"):
        return str(value)
    return value


def _dataclass_json(value: Any) -> dict[str, Any]:
    from dataclasses import asdict

    normalized = _normalize(asdict(value))
    if not isinstance(normalized, dict):
        raise TypeError("dataclass serialization must produce an object")
    return normalized
