from intelligence.macro_regime import score_macro_regime


def test_macro_regime_classifies_risk_on() -> None:
    score = score_macro_regime({"liquidity": 0.8, "rates": 0.7, "volatility": 0.6})

    assert score.classification == "RISK_ON"
    assert score.confidence == 1.0
    assert score.to_dict()["can_execute_trades"] is False


def test_macro_regime_missing_data_is_insufficient() -> None:
    score = score_macro_regime({})

    assert score.classification == "INSUFFICIENT_DATA"
    assert score.confidence == 0.0

