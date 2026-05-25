"""Deterministic risk-adjusted score calculation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RiskAdjustedScore:
    risk_adjusted_score: float
    confidence: float
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_adjusted_score": self.risk_adjusted_score,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


def calculate_risk_adjusted_score(
    *,
    opportunity_score: float,
    risk_score: float,
    liquidity_score: float,
    confidence: float,
) -> RiskAdjustedScore:
    """Combine opportunity, risk, liquidity, and confidence into a bounded score."""

    opportunity = _bounded(opportunity_score)
    risk = _bounded(risk_score)
    liquidity = _bounded(liquidity_score)
    conf = max(0.0, min(1.0, float(confidence)))
    reasons = ["RISK_ADJUSTED_SCORE_CALCULATED"]
    score = opportunity * (1.0 - risk / 100.0) * conf

    if liquidity < 20:
        score = min(score, 20.0)
        reasons.append("LIQUIDITY_CRITICAL_CAP")
    elif liquidity < 40:
        score = min(score, 40.0)
        reasons.append("LIQUIDITY_LOW_CAP")

    if risk >= 75:
        score = min(score, 25.0)
        reasons.append("HIGH_RISK_CAP")

    return RiskAdjustedScore(round(max(0.0, min(100.0, score)), 4), round(conf, 4), tuple(reasons))


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, float(value)))
