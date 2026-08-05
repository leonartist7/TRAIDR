from scoring.shadow_promotion import ShadowPromotionEvidence, evaluate_shadow_promotion


def _passing_evidence() -> ShadowPromotionEvidence:
    return ShadowPromotionEvidence(
        coverage=0.96,
        walk_forward_folds=3,
        independent_outcomes=500,
        baseline_brier=0.20,
        candidate_brier=0.19,
        baseline_ece=0.04,
        candidate_ece=0.05,
        baseline_net_expectancy=0.2,
        candidate_net_expectancy=0.21,
        baseline_max_drawdown=-10.0,
        candidate_max_drawdown=-11.0,
        replay_hashes_identical=True,
        safety_regressions=0,
        secret_exposure_regressions=0,
    )


def test_all_promotion_gates_only_allow_human_review_and_keep_zero_weight() -> None:
    decision = evaluate_shadow_promotion(_passing_evidence())

    assert decision.eligible is True
    assert decision.status == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert decision.scoring_weight == 0.0
    assert decision.can_execute_trades is False


def test_any_failed_gate_keeps_feature_in_shadow_mode() -> None:
    evidence = _passing_evidence()
    failed = ShadowPromotionEvidence(
        **{
            **evidence.__dict__,
            "independent_outcomes": 499,
            "candidate_brier": 0.199,
            "replay_hashes_identical": False,
            "safety_regressions": 1,
        }
    )
    decision = evaluate_shadow_promotion(failed)

    assert decision.eligible is False
    assert decision.status == "SHADOW_ONLY"
    assert decision.scoring_weight == 0.0
    assert "PROMOTION_OUTCOMES_BELOW_500" in decision.reason_codes
    assert "PROMOTION_REPLAY_HASH_MISMATCH" in decision.reason_codes
    assert "PROMOTION_SAFETY_REGRESSION" in decision.reason_codes
