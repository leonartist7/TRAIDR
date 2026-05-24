"""Deterministic opportunity state transitions."""

from __future__ import annotations

from radar.models import OpportunityState


def classify_opportunity(
    *,
    opportunity_score: float,
    risk_score: float,
    confidence: float,
    missing_critical_count: int = 0,
    conflict_detected: bool = False,
) -> tuple[OpportunityState, tuple[str, ...]]:
    reasons: list[str] = []
    if risk_score >= 75:
        return OpportunityState.AVOID, ("HIGH_RISK_OVERRIDES_OPPORTUNITY",)
    if missing_critical_count:
        reasons.append("CONFIDENCE_REDUCED_BY_MISSING_DATA")
    if conflict_detected:
        reasons.append("CONFLICTING_MARKET_SIGNALS")
    if confidence < 0.35:
        return OpportunityState.ALERT, tuple((*reasons, "LOW_CONFIDENCE_ALERT"))
    if opportunity_score >= 70 and risk_score < 50 and confidence >= 0.55:
        return OpportunityState.BUY_CANDIDATE, tuple((*reasons, "BUY_CANDIDATE_RESEARCH_ONLY"))
    if opportunity_score <= 25 and risk_score >= 50:
        return OpportunityState.SELL_CANDIDATE, tuple((*reasons, "SELL_CANDIDATE_RESEARCH_ONLY"))
    if reasons:
        return OpportunityState.ALERT, tuple(reasons)
    return OpportunityState.WATCH, ("WATCHLIST_MONITORING",)

