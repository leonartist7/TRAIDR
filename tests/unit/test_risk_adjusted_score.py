from scoring.risk_adjusted_score import calculate_risk_adjusted_score


def test_risk_adjusted_score_is_deterministic() -> None:
    first = calculate_risk_adjusted_score(
        opportunity_score=80,
        risk_score=25,
        liquidity_score=70,
        confidence=0.8,
    )
    second = calculate_risk_adjusted_score(
        opportunity_score=80,
        risk_score=25,
        liquidity_score=70,
        confidence=0.8,
    )

    assert first == second
    assert first.risk_adjusted_score == 48.0
    assert first.to_dict()["can_execute_trades"] is False


def test_low_liquidity_caps_risk_adjusted_score() -> None:
    score = calculate_risk_adjusted_score(
        opportunity_score=100,
        risk_score=5,
        liquidity_score=25,
        confidence=1,
    )

    assert score.risk_adjusted_score == 40.0
    assert "LIQUIDITY_LOW_CAP" in score.reason_codes
