from risk.anti_rug import assess_anti_rug
from risk.models import AntiRugEvidence


def safe_evidence(**overrides: bool | None) -> AntiRugEvidence:
    values: dict[str, bool | None] = {
        "liquidity_accessible": True,
        "liquidity_meets_floor": True,
        "liquidity_status_known": True,
        "mint_freeze_or_sell_restriction": False,
        "unsafe_holder_or_creator_control": False,
        "honeypot_tax_route_or_sellability_issue": False,
        "identity_ambiguous": False,
        "evidence_complete": True,
    }
    values.update(overrides)
    return AntiRugEvidence(**values)


def test_anti_rug_hard_fail_flags_liquidity_and_honeypot_signals() -> None:
    assessment = assess_anti_rug(
        safe_evidence(
            liquidity_meets_floor=False,
            honeypot_tax_route_or_sellability_issue=True,
        )
    )

    assert assessment.hard_failed is True
    assert assessment.hard_fail_reasons == (
        "ANTI_RUG_HONEYPOT_OR_SELLABILITY",
        "ANTI_RUG_LIQUIDITY_BELOW_FLOOR",
    )
    assert assessment.insufficient_data is False


def test_anti_rug_unknown_required_evidence_is_insufficient_data() -> None:
    assessment = assess_anti_rug(safe_evidence(liquidity_status_known=None))

    assert assessment.hard_failed is False
    assert assessment.insufficient_data is True
    assert assessment.insufficient_data_reasons == ("ANTI_RUG_EVIDENCE_INSUFFICIENT",)

