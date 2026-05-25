"""Models for non-executing candidate lifecycle tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class CandidateLifecycleState(StrEnum):
    DISCOVERED = "DISCOVERED"
    WATCH = "WATCH"
    ALERT = "ALERT"
    BUY_CANDIDATE = "BUY_CANDIDATE"
    REVIEW = "REVIEW"
    AVOID = "AVOID"
    STALE = "STALE"
    EXIT_RISK = "EXIT_RISK"


@dataclass(frozen=True)
class CandidateSnapshot:
    subject_id: str
    state: CandidateLifecycleState
    observed_at: datetime
    opportunity_score: float
    risk_score: float
    liquidity_score: float
    data_quality_score: float
    appearance_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "state": self.state.value,
            "observed_at": self.observed_at.isoformat(),
            "opportunity_score": self.opportunity_score,
            "risk_score": self.risk_score,
            "liquidity_score": self.liquidity_score,
            "data_quality_score": self.data_quality_score,
            "appearance_count": self.appearance_count,
            "can_execute_trades": False,
        }


@dataclass(frozen=True)
class LifecycleEvent:
    subject_id: str
    event_type: str
    from_state: CandidateLifecycleState | None
    to_state: CandidateLifecycleState
    observed_at: datetime
    reason_codes: tuple[str, ...]
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "event_type": self.event_type,
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value,
            "observed_at": self.observed_at.isoformat(),
            "reason_codes": list(self.reason_codes),
            "payload": self.payload,
            "can_execute_trades": False,
        }
