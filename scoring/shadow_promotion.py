"""Deterministic promotion gates for zero-weight shadow evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShadowPromotionEvidence:
    coverage: float
    walk_forward_folds: int
    independent_outcomes: int
    baseline_brier: float
    candidate_brier: float
    baseline_ece: float
    candidate_ece: float
    baseline_net_expectancy: float
    candidate_net_expectancy: float
    baseline_max_drawdown: float
    candidate_max_drawdown: float
    replay_hashes_identical: bool
    safety_regressions: int
    secret_exposure_regressions: int


@dataclass(frozen=True)
class ShadowPromotionDecision:
    eligible: bool
    scoring_weight: float
    status: str
    relative_brier_improvement: float | None
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False


def evaluate_shadow_promotion(evidence: ShadowPromotionEvidence) -> ShadowPromotionDecision:
    """Require every accuracy, replay, risk, and safety gate before promotion review."""

    reasons: list[str] = []
    if evidence.coverage < 0.95:
        reasons.append("PROMOTION_COVERAGE_BELOW_95_PERCENT")
    if evidence.walk_forward_folds < 3:
        reasons.append("PROMOTION_WALK_FORWARD_FOLDS_BELOW_3")
    if evidence.independent_outcomes < 500:
        reasons.append("PROMOTION_OUTCOMES_BELOW_500")
    relative_brier = None
    if evidence.baseline_brier <= 0:
        reasons.append("PROMOTION_BASELINE_BRIER_INVALID")
    else:
        relative_brier = (evidence.baseline_brier - evidence.candidate_brier) / evidence.baseline_brier
        if relative_brier < 0.03:
            reasons.append("PROMOTION_BRIER_IMPROVEMENT_BELOW_3_PERCENT")
    if evidence.candidate_ece - evidence.baseline_ece > 0.0100000001:
        reasons.append("PROMOTION_ECE_WORSENED")
    if evidence.candidate_net_expectancy < evidence.baseline_net_expectancy:
        reasons.append("PROMOTION_NET_EXPECTANCY_DECREASED")
    allowed_drawdown = abs(evidence.baseline_max_drawdown) * 1.10
    if abs(evidence.candidate_max_drawdown) > allowed_drawdown:
        reasons.append("PROMOTION_MAX_DRAWDOWN_WORSENED")
    if not evidence.replay_hashes_identical:
        reasons.append("PROMOTION_REPLAY_HASH_MISMATCH")
    if evidence.safety_regressions:
        reasons.append("PROMOTION_SAFETY_REGRESSION")
    if evidence.secret_exposure_regressions:
        reasons.append("PROMOTION_SECRET_EXPOSURE_REGRESSION")

    eligible = not reasons
    return ShadowPromotionDecision(
        eligible=eligible,
        scoring_weight=0.0,
        status="ELIGIBLE_FOR_HUMAN_REVIEW" if eligible else "SHADOW_ONLY",
        relative_brier_improvement=relative_brier,
        reason_codes=tuple(reasons) if reasons else ("ALL_SHADOW_PROMOTION_GATES_PASSED",),
    )
