"""Typed outputs for non-executing opportunity radar."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OpportunityState(str, Enum):
    WATCH = "WATCH"
    ALERT = "ALERT"
    BUY_CANDIDATE = "BUY_CANDIDATE"
    SELL_CANDIDATE = "SELL_CANDIDATE"
    AVOID = "AVOID"


@dataclass(frozen=True)
class RadarCandidate:
    subject_id: str
    state: OpportunityState
    rank: int
    opportunity_score: float
    risk_score: float
    confidence: float
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "state": self.state.value,
            "rank": self.rank,
            "opportunity_score": self.opportunity_score,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }

