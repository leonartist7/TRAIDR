from thesis.generator import generate_research_thesis
from thesis.models import ThesisInputs


def test_thesis_generator_outputs_structured_research_notes() -> None:
    thesis = generate_research_thesis(
        ThesisInputs(
            subject_id="fixture-sol-usdc",
            radar_state="ALERT",
            opportunity_score=68,
            risk_score=35,
            risk_adjusted_score=52,
            confidence=0.72,
            liquidity_score=75,
            technical_score=70,
            safety_status="CLEAR",
            reason_codes=("RADAR_ALERT",),
        )
    )

    assert thesis.thesis_summary
    assert thesis.opportunity_drivers
    assert thesis.risk_factors
    assert thesis.invalidation_conditions
    assert thesis.watch_conditions
    assert thesis.exit_warning_conditions
    assert thesis.confidence == 0.72
    assert thesis.can_execute_trades is False
    assert thesis.to_dict()["can_execute_trades"] is False
    assert "RADAR_ALERT" in thesis.reason_codes


def test_thesis_generator_calls_out_missing_data() -> None:
    thesis = generate_research_thesis(
        ThesisInputs(
            subject_id="fixture-unknown",
            confidence=0.9,
            data_gaps=("NO_MARKET_SCAN_DATA",),
        )
    )

    assert thesis.confidence <= 0.35
    assert "incomplete research context" in thesis.thesis_summary
    assert "NO_MARKET_SCAN_DATA" in thesis.data_gaps
    assert "MISSING_RADAR_STATE" in thesis.data_gaps
    assert thesis.risk_factors
    assert thesis.invalidation_conditions
    assert "THESIS_DATA_GAPS_PRESENT" in thesis.reason_codes


def test_thesis_generator_avoids_financial_advice_language() -> None:
    thesis = generate_research_thesis(
        ThesisInputs(
            subject_id="fixture-sol-usdc",
            radar_state="BUY_CANDIDATE",
            opportunity_score=80,
            risk_score=20,
            risk_adjusted_score=60,
            confidence=0.8,
            liquidity_score=80,
            technical_score=80,
            safety_status="CLEAR",
        )
    )
    text = " ".join(
        (
            thesis.thesis_summary,
            *thesis.opportunity_drivers,
            *thesis.risk_factors,
            *thesis.invalidation_conditions,
            *thesis.watch_conditions,
            *thesis.exit_warning_conditions,
        )
    ).lower()

    assert "financial advice" not in text
    assert "should buy" not in text
    assert "recommend buying" not in text
