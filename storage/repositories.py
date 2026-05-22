"""Minimal safe repositories for DuckDB research and audit records."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import duckdb

from utils.toon import JsonValue, assert_safe_payload, serialize_toon


class RepositoryWriteError(RuntimeError):
    """Raised when a repository refuses or cannot write a record."""


class ResearchRepository:
    """Persist scrubbed research evidence and decisions."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def record_evidence(
        self,
        *,
        source_name: str,
        observed_at: datetime,
        quality_status: str,
        payload: Mapping[str, JsonValue],
        provenance: Mapping[str, JsonValue],
        collected_at: datetime | None = None,
    ) -> str:
        snapshot_id = _new_id("evidence")
        self.connection.execute(
            """
            INSERT INTO evidence_snapshots (
                snapshot_id,
                source_name,
                observed_at,
                collected_at,
                quality_status,
                payload_json,
                provenance_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                snapshot_id,
                source_name,
                _require_aware_datetime(observed_at),
                _require_aware_datetime(collected_at or _utc_now()),
                quality_status,
                _safe_json(payload),
                _safe_json(provenance),
            ],
        )
        return snapshot_id

    def record_vector(
        self,
        *,
        snapshot_id: str | None,
        feature_status: str,
        features: Mapping[str, JsonValue],
        created_at: datetime | None = None,
    ) -> str:
        vector_id = _new_id("vector")
        self.connection.execute(
            """
            INSERT INTO technical_vectors (
                vector_id,
                snapshot_id,
                created_at,
                feature_status,
                features_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                vector_id,
                snapshot_id,
                _require_aware_datetime(created_at or _utc_now()),
                feature_status,
                _safe_json(features),
            ],
        )
        return vector_id

    def record_intent(
        self,
        *,
        intent: str,
        output_status: str,
        reason_codes: Sequence[str],
        payload: Mapping[str, JsonValue],
        created_at: datetime | None = None,
    ) -> str:
        intent_id = _new_id("intent")
        self.connection.execute(
            """
            INSERT INTO research_intents (
                intent_id,
                created_at,
                intent,
                output_status,
                reason_codes_json,
                payload_toon
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                intent_id,
                _require_aware_datetime(created_at or _utc_now()),
                intent,
                output_status,
                _safe_json(list(reason_codes)),
                serialize_toon(payload),
            ],
        )
        return intent_id

    def record_risk_decision(
        self,
        *,
        decision: str,
        reason_codes: Sequence[str],
        details: Mapping[str, JsonValue],
        intent_id: str | None = None,
        decided_at: datetime | None = None,
    ) -> str:
        decision_id = _new_id("risk")
        self.connection.execute(
            """
            INSERT INTO risk_decisions (
                decision_id,
                intent_id,
                decided_at,
                decision,
                reason_codes_json,
                details_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                decision_id,
                intent_id,
                _require_aware_datetime(decided_at or _utc_now()),
                decision,
                _safe_json(list(reason_codes)),
                _safe_json(details),
            ],
        )
        return decision_id


class SimulationRepository:
    """Persist only paper-order storage records; execution belongs to later phases."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def record_order(
        self,
        *,
        risk_decision_id: str,
        side: str,
        pair_id: str,
        notional_usd: Decimal,
        order_status: str,
        metadata: Mapping[str, JsonValue],
        created_at: datetime | None = None,
    ) -> str:
        order_id = _new_id("paper_order")
        self.connection.execute(
            """
            INSERT INTO simulated_orders (
                order_id,
                risk_decision_id,
                created_at,
                side,
                pair_id,
                notional_usd,
                order_status,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                order_id,
                risk_decision_id,
                _require_aware_datetime(created_at or _utc_now()),
                side,
                pair_id,
                notional_usd,
                order_status,
                _safe_json(metadata),
            ],
        )
        return order_id

    def record_fill(
        self,
        *,
        order_id: str,
        quantity: Decimal,
        price_usd: Decimal,
        notional_usd: Decimal,
        metadata: Mapping[str, JsonValue],
        filled_at: datetime | None = None,
    ) -> str:
        fill_id = _new_id("paper_fill")
        self.connection.execute(
            """
            INSERT INTO simulated_fills (
                fill_id,
                order_id,
                filled_at,
                quantity,
                price_usd,
                notional_usd,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                fill_id,
                order_id,
                _require_aware_datetime(filled_at or _utc_now()),
                quantity,
                price_usd,
                notional_usd,
                _safe_json(metadata),
            ],
        )
        return fill_id


class AuditRepository:
    """Persist structured local audit events with safe JSON payloads."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def append_event(
        self,
        *,
        event_type: str,
        severity: str,
        reason_codes: Sequence[str],
        payload: Mapping[str, JsonValue],
        recorded_at: datetime | None = None,
    ) -> str:
        event_id = _new_id("audit")
        self.connection.execute(
            """
            INSERT INTO audit_events (
                event_id,
                recorded_at,
                event_type,
                severity,
                reason_codes_json,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                event_id,
                _require_aware_datetime(recorded_at or _utc_now()),
                event_type,
                severity,
                _safe_json(list(reason_codes)),
                _safe_json(payload),
            ],
        )
        return event_id


def _safe_json(value: Any) -> str:
    try:
        assert_safe_payload(value)
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise RepositoryWriteError("unsafe or unsupported storage payload") from exc


def _require_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RepositoryWriteError("storage timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

