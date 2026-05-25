"""Models for structured research thesis notes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ThesisInputs:
    subject_id: str
    radar_state: str | None = None
    opportunity_score: float | None = None
    risk_score: float | None = None
    risk_adjusted_score: float | None = None
    confidence: float | None = None
    liquidity_score: float | None = None
    technical_score: float | None = None
    safety_status: str | None = None
    reason_codes: tuple[str, ...] = ()
    data_gaps: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchThesis:
    subject_id: str
    thesis_summary: str
    opportunity_drivers: tuple[str, ...]
    risk_factors: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    watch_conditions: tuple[str, ...]
    exit_warning_conditions: tuple[str, ...]
    confidence: float
    data_gaps: tuple[str, ...]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "thesis_summary": self.thesis_summary,
            "opportunity_drivers": list(self.opportunity_drivers),
            "risk_factors": list(self.risk_factors),
            "invalidation_conditions": list(self.invalidation_conditions),
            "watch_conditions": list(self.watch_conditions),
            "exit_warning_conditions": list(self.exit_warning_conditions),
            "confidence": self.confidence,
            "data_gaps": list(self.data_gaps),
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }
