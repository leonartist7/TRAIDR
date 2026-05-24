"""Chief investment officer aggregation agent; analysis only."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from agents.opportunity_ranker import OpportunityRanking, rank_opportunity


class CIORecommendation(str, Enum):
    WATCH = "WATCH"
    ALERT = "ALERT"
    BUY_CANDIDATE = "BUY_CANDIDATE"
    SELL_CANDIDATE = "SELL_CANDIDATE"
    AVOID = "AVOID"


@dataclass(frozen=True)
class CIODecision:
    recommendation: CIORecommendation
    ranking: OpportunityRanking
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation": self.recommendation.value,
            "ranking": self.ranking.to_dict(),
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


class CIOAgent:
    name = "cio"

    def analyze(self, analyses: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        return self.decide(analyses).to_dict()

    def decide(self, analyses: Iterable[Mapping[str, Any]]) -> CIODecision:
        ranking = rank_opportunity(analyses)
        reasons = list(ranking.reason_codes)
        if ranking.risk_score >= 75:
            recommendation = CIORecommendation.AVOID
            reasons.append("HIGH_RISK_OVERRIDES_OPPORTUNITY")
        elif ranking.missing_critical_count:
            recommendation = CIORecommendation.ALERT
            reasons.append("CONFIDENCE_REDUCED_BY_MISSING_DATA")
        elif ranking.conflict_detected:
            recommendation = CIORecommendation.ALERT
            reasons.append("CONFLICTING_AGENT_SIGNALS")
        elif ranking.opportunity_score >= 70 and ranking.confidence >= 0.55 and ranking.risk_score < 50:
            recommendation = CIORecommendation.BUY_CANDIDATE
            reasons.append("STRONG_OPPORTUNITY_LOW_RISK")
        elif ranking.opportunity_score <= 25 and ranking.risk_score >= 50:
            recommendation = CIORecommendation.SELL_CANDIDATE
            reasons.append("WEAK_OPPORTUNITY_ELEVATED_RISK")
        else:
            recommendation = CIORecommendation.WATCH
            reasons.append("WATCHLIST_ONLY")
        return CIODecision(recommendation, ranking, tuple(dict.fromkeys(reasons)))
