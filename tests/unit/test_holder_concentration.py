from decimal import Decimal

from onchain.holder_concentration import analyze_holder_concentration
from onchain.rug_observations import to_anti_rug_evidence
from risk.anti_rug import assess_anti_rug


def test_unknown_holder_distribution_is_insufficient_data() -> None:
    result = analyze_holder_concentration(None)

    assert result.ok is False
    assert result.reason_codes == ("HOLDER_DISTRIBUTION_UNKNOWN",)


def test_high_top_holder_concentration_is_hard_fail() -> None:
    result = analyze_holder_concentration(
        [Decimal("0.40"), Decimal("0.05"), Decimal("0.04")]
    )
    assert result.value is not None
    evidence = to_anti_rug_evidence(result.value.to_observation())
    assessment = assess_anti_rug(evidence)

    assert result.value.unsafe_holder_or_creator_control is True
    assert result.value.reason_codes == ("TOP_HOLDER_CONCENTRATION_HARD_FAIL",)
    assert assessment.hard_fail_reasons == ("ANTI_RUG_HOLDER_OR_CREATOR_CONTROL",)


def test_acceptable_holder_distribution_maps_control_false_only() -> None:
    result = analyze_holder_concentration(
        [Decimal("0.10"), Decimal("0.09"), Decimal("0.08"), Decimal("0.07")]
    )
    assert result.value is not None
    evidence = to_anti_rug_evidence(result.value.to_observation())

    assert result.value.reason_codes == ("HOLDER_CONCENTRATION_ACCEPTABLE",)
    assert evidence.unsafe_holder_or_creator_control is False
    assert evidence.liquidity_accessible is None
