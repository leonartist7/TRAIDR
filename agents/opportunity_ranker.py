"""Combine structured agent analyses into opportunity and risk scores."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpportunityRanking:
    opportunity_score: float
    risk_score: float
    confidence: float
    missing_critical_count: int
    conflict_detected: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, float | int | bool | list[str]]:
        return {
            "opportunity_score": self.opportunity_score,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "missing_critical_count": self.missing_critical_count,
            "conflict_detected": self.conflict_detected,
            "reason_codes": list(self.reason_codes),
        }


def rank_opportunity(analyses: Iterable[Mapping[str, Any]]) -> OpportunityRanking:
    rows = tuple(analyses)
    if not rows:
        return OpportunityRanking(0.0, 75.0, 0.0, 1, False, ("AGENT_ANALYSES_MISSING",))

    missing = sum(1 for row in rows if row.get("status") == "INSUFFICIENT_DATA")
    scores = [_num(row.get("score")) for row in rows]
    risks = [_num(row.get("risk_score")) for row in rows]
    confidences = [_num(row.get("confidence")) for row in rows]
    available = [score for score in scores if score is not None]
    available_risks = [risk for risk in risks if risk is not None]
    available_confidences = [confidence for confidence in confidences if confidence is not None]

    opportunity = sum(available) / len(available) if available else 0.0
    risk = max(available_risks) if available_risks else 75.0
    base_confidence = sum(available_confidences) / len(available_confidences) if available_confidences else 0.0
    confidence = max(0.0, base_confidence - missing * 0.15)
    high_scores = any(score >= 75 for score in available)
    elevated_risks = any(risk >= 70 for risk in available_risks)
    high_risks = any(risk >= 75 for risk in available_risks)
    conflict = high_scores and elevated_risks
    reasons: list[str] = []
    if missing:
        reasons.append("CRITICAL_DATA_MISSING")
    if conflict:
        reasons.append("AGENT_CONFLICT_DETECTED")
    if high_risks:
        reasons.append("HIGH_RISK_SIGNAL_PRESENT")
    if not reasons:
        reasons.append("AGENT_RANKING_COMPLETE")

    return OpportunityRanking(
        opportunity_score=round(opportunity, 4),
        risk_score=round(risk, 4),
        confidence=round(confidence, 4),
        missing_critical_count=missing,
        conflict_detected=conflict,
        reason_codes=tuple(reasons),
    )


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
