"""Append-only DuckDB lifecycle tracker."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import duckdb

from lifecycle.models import CandidateSnapshot, LifecycleEvent
from lifecycle.transitions import detect_lifecycle_events
from utils.toon import assert_safe_payload


class LifecycleTracker:
    """Track and optionally persist lifecycle events for radar candidates."""

    def __init__(self, connection: duckdb.DuckDBPyConnection | None = None) -> None:
        self.connection = connection

    def track(
        self,
        *,
        previous: CandidateSnapshot | None,
        current: CandidateSnapshot | None,
        now: datetime | None = None,
    ) -> tuple[LifecycleEvent, ...]:
        events = detect_lifecycle_events(previous=previous, current=current, now=now)
        if self.connection is not None:
            for event in events:
                self.record_event(event)
        return events

    def record_event(self, event: LifecycleEvent) -> str:
        if self.connection is None:
            raise RuntimeError("LifecycleTracker has no DuckDB connection")
        event_id = f"lifecycle_{uuid4().hex}"
        self.connection.execute(
            """
            INSERT INTO lifecycle_events (
                event_id,
                recorded_at,
                subject_id,
                event_type,
                from_state,
                to_state,
                reason_codes_json,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_id,
                _aware(event.observed_at),
                event.subject_id,
                event.event_type,
                event.from_state.value if event.from_state else None,
                event.to_state.value,
                _safe_json(list(event.reason_codes)),
                _safe_json(event.to_dict()),
            ],
        )
        return event_id


def latest_snapshot_from_row(row: dict[str, Any]) -> CandidateSnapshot:
    """Build a candidate snapshot from local dashboard/radar style rows."""

    from lifecycle.models import CandidateLifecycleState

    return CandidateSnapshot(
        subject_id=str(row["subject_id"]),
        state=CandidateLifecycleState(str(row.get("state") or "WATCH")),
        observed_at=_aware(row.get("observed_at") or row.get("recorded_at") or datetime.now(timezone.utc)),
        opportunity_score=float(row.get("opportunity_score") or 0),
        risk_score=float(row.get("risk_score") or 100),
        liquidity_score=float(row.get("liquidity_score") or 0),
        data_quality_score=float(row.get("data_quality_score") or 0),
        appearance_count=int(row.get("appearance_count") or 1),
    )


def _safe_json(value: Any) -> str:
    assert_safe_payload(value)
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
