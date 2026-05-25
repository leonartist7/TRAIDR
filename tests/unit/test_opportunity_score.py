from scoring.opportunity_score import OpportunityScoreInputs, score_opportunity_v2


def test_opportunity_score_v2_outputs_all_scores() -> None:
    result = score_opportunity_v2(
        OpportunityScoreInputs(
            liquidity_score=80,
            volume_score=70,
            technical_score=75,
            safety_score=90,
            wallet_score=60,
            sentiment_score=55,
            macro_score=50,
            data_quality_score=95,
        )
    )

    assert result.opportunity_score > 70
    assert result.risk_score < 30
    assert result.risk_adjusted_score > 45
    assert result.confidence > 0.8
    assert result.to_dict()["can_execute_trades"] is False


def test_high_rug_risk_caps_opportunity_score() -> None:
    result = score_opportunity_v2(
        OpportunityScoreInputs(
            liquidity_score=90,
            volume_score=90,
            technical_score=90,
            safety_score=20,
            wallet_score=90,
            sentiment_score=90,
            macro_score=90,
            data_quality_score=90,
        )
    )

    assert result.opportunity_score <= 25
    assert "RUG_RISK_OPPORTUNITY_CAP" in result.reason_codes


def test_missing_safety_caps_confidence_and_is_not_bullish() -> None:
    result = score_opportunity_v2(
        OpportunityScoreInputs(
            liquidity_score=90,
            volume_score=90,
            technical_score=90,
            safety_score=None,
            data_quality_score=90,
        )
    )

    assert result.confidence <= 0.35
    assert result.opportunity_score <= 35
    assert "MISSING_SAFETY_CONFIDENCE_CAP" in result.reason_codes
    assert "OPTIONAL_WALLET_SCORE_MISSING" in result.reason_codes
