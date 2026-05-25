"""Opportunity score v2 for non-executing radar research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scoring.reason_explainer import explain_reasons
from scoring.risk_adjusted_score import calculate_risk_adjusted_score


@dataclass(frozen=True)
class OpportunityScoreInputs:
    liquidity_score: float
    volume_score: float
    technical_score: float
    safety_score: float | None
    data_quality_score: float
    wallet_score: float | None = None
    sentiment_score: float | None = None
    macro_score: float | None = None


@dataclass(frozen=True)
class OpportunityScoreV2:
    opportunity_score: float
    risk_score: float
    risk_adjusted_score: float
    confidence: float
    reason_codes: tuple[str, ...]
    human_explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_score": self.opportunity_score,
            "risk_score": self.risk_score,
            "risk_adjusted_score": self.risk_adjusted_score,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "human_explanation": self.human_explanation,
            "can_execute_trades": False,
        }


def score_opportunity_v2(inputs: OpportunityScoreInputs) -> OpportunityScoreV2:
    """Build deterministic risk-adjusted research scores."""

    liquidity = _bounded(inputs.liquidity_score)
    volume = _bounded(inputs.volume_score)
    technical = _bounded(inputs.technical_score)
    safety = None if inputs.safety_score is None else _bounded(inputs.safety_score)
    data_quality = _bounded(inputs.data_quality_score)
    wallet = _optional(inputs.wallet_score)
    sentiment = _optional(inputs.sentiment_score)
    macro = _optional(inputs.macro_score)
    reasons = ["OPPORTUNITY_SCORE_V2_CALCULATED"]

    base_components = [
        liquidity * 0.18,
        volume * 0.14,
        technical * 0.22,
        (safety or 0.0) * 0.28,
        data_quality * 0.18,
    ]
    optional_bonus = wallet * 0.05 + sentiment * 0.04 + macro * 0.03
    opportunity = sum(base_components) + optional_bonus

    if inputs.wallet_score is None:
        reasons.append("OPTIONAL_WALLET_SCORE_MISSING")
    if inputs.sentiment_score is None:
        reasons.append("OPTIONAL_SENTIMENT_SCORE_MISSING")
    if inputs.macro_score is None:
        reasons.append("OPTIONAL_MACRO_SCORE_MISSING")

    safety_missing = safety is None
    if safety_missing:
        confidence = 0.35
        opportunity = min(opportunity, 35.0)
        reasons.append("MISSING_SAFETY_CONFIDENCE_CAP")
    else:
        confidence = 0.45 + data_quality / 200.0

    if safety is not None and safety < 30:
        opportunity = min(opportunity, 25.0)
        reasons.append("RUG_RISK_OPPORTUNITY_CAP")
    elif safety is not None and safety < 50:
        opportunity = min(opportunity, 45.0)
        reasons.append("SAFETY_WEAK_OPPORTUNITY_CAP")

    if data_quality < 50:
        confidence = min(confidence, 0.45)
        reasons.append("DATA_QUALITY_CONFIDENCE_CAP")

    risk_score = _risk_score(liquidity=liquidity, safety=safety, data_quality=data_quality, technical=technical)
    adjusted = calculate_risk_adjusted_score(
        opportunity_score=opportunity,
        risk_score=risk_score,
        liquidity_score=liquidity,
        confidence=confidence,
    )
    reason_codes = tuple(dict.fromkeys((*reasons, *adjusted.reason_codes)))
    return OpportunityScoreV2(
        opportunity_score=round(max(0.0, min(100.0, opportunity)), 4),
        risk_score=round(risk_score, 4),
        risk_adjusted_score=adjusted.risk_adjusted_score,
        confidence=adjusted.confidence,
        reason_codes=reason_codes,
        human_explanation=explain_reasons(reason_codes),
    )


def _risk_score(*, liquidity: float, safety: float | None, data_quality: float, technical: float) -> float:
    safety_risk = 100.0 if safety is None else 100.0 - safety
    liquidity_risk = 100.0 - liquidity
    quality_risk = 100.0 - data_quality
    technical_risk = max(0.0, 50.0 - technical)
    return max(0.0, min(100.0, safety_risk * 0.45 + liquidity_risk * 0.25 + quality_risk * 0.2 + technical_risk * 0.1))


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _optional(value: float | None) -> float:
    return 0.0 if value is None else _bounded(value)
