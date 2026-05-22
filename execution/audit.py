"""Audit helpers for every simulation execution attempt."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from execution.models import SimulationOrderRequest
from storage.repositories import AuditRepository
from utils.toon import JsonValue


class ExecutionAudit:
    """Persist paper execution events through the local audit repository."""

    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def record(
        self,
        *,
        event_type: str,
        reason_codes: Sequence[str],
        request: SimulationOrderRequest,
        payload: dict[str, JsonValue] | None = None,
        severity: str = "INFO",
        recorded_at: datetime | None = None,
    ) -> str:
        base_payload: dict[str, JsonValue] = {
            "mode": request.mode,
            "pair_id": request.pair_id,
            "risk_decision_id": request.risk_decision_id,
            "risk_outcome": request.risk_decision.outcome.value,
            "side": request.side.value,
        }
        if payload:
            base_payload.update(payload)
        return self.repository.append_event(
            event_type=event_type,
            severity=severity,
            reason_codes=tuple(reason_codes),
            payload=base_payload,
            recorded_at=recorded_at,
        )

