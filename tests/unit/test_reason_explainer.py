from scoring.reason_explainer import explain_reasons


def test_reason_explainer_returns_human_text_and_safety_boundary() -> None:
    explanation = explain_reasons(("RUG_RISK_OPPORTUNITY_CAP", "LIQUIDITY_LOW_CAP"))

    assert "rug" in explanation.lower()
    assert "liquidity" in explanation.lower()
    assert "cannot execute trades" in explanation


def test_reason_explainer_handles_unknown_reasons() -> None:
    explanation = explain_reasons(("CUSTOM_REASON",))

    assert "Custom reason." in explanation
