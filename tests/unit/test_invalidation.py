from thesis.invalidation import build_exit_warning_conditions, build_invalidation_conditions
from thesis.models import ThesisInputs


def test_invalidation_conditions_are_always_present() -> None:
    conditions = build_invalidation_conditions(
        ThesisInputs(
            subject_id="fixture-sol-usdc",
            radar_state="WATCH",
            opportunity_score=55,
            risk_score=30,
            liquidity_score=70,
            safety_status="CLEAR",
        )
    )

    assert conditions
    assert any("Anti-rug" in condition for condition in conditions)


def test_invalidation_reflects_low_liquidity_and_high_risk() -> None:
    inputs = ThesisInputs(
        subject_id="fixture-sol-usdc",
        risk_score=80,
        risk_adjusted_score=20,
        liquidity_score=20,
        safety_status="UNKNOWN",
    )

    invalidation = build_invalidation_conditions(inputs)
    exit_warnings = build_exit_warning_conditions(inputs)

    assert any("Liquidity remains thin" in condition for condition in invalidation)
    assert any("Risk score stays elevated" in condition for condition in invalidation)
    assert any("Risk-adjusted score remains weak" in condition for condition in exit_warnings)
    assert any("Risk score is already high" in condition for condition in exit_warnings)
