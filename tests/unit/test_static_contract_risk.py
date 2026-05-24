from onchain.rug_observations import to_anti_rug_evidence
from onchain.static_contract_risk import analyze_static_contract_risk
from risk.anti_rug import assess_anti_rug


def test_static_contract_risk_requires_optional_json_input() -> None:
    result = analyze_static_contract_risk(None)

    assert result.ok is False
    assert result.reason_codes == ("STATIC_SCANNER_OUTPUT_MISSING",)


def test_mint_freeze_and_owner_privileges_map_to_anti_rug_hard_fail() -> None:
    result = analyze_static_contract_risk(
        {
            "flags": {
                "mint_authority": True,
                "freeze_authority": False,
                "owner_can_change_fees": True,
                "owner_can_blacklist": False,
                "honeypot": False,
                "sell_tax_high": False,
                "transfer_restricted": False,
            }
        }
    )
    assert result.value is not None
    evidence = to_anti_rug_evidence(result.value.to_observation())
    assessment = assess_anti_rug(evidence)

    assert result.value.reason_codes == (
        "STATIC_MINT_OR_FREEZE_PRIVILEGE",
        "STATIC_OWNER_CONTROL_PRIVILEGE",
    )
    assert assessment.hard_fail_reasons == (
        "ANTI_RUG_MINT_FREEZE_OR_SELL_RESTRICTION",
        "ANTI_RUG_HOLDER_OR_CREATOR_CONTROL",
    )


def test_unknown_static_fields_remain_unknown_not_bullish() -> None:
    result = analyze_static_contract_risk({"flags": {"mint_authority": False}})
    assert result.value is not None
    evidence = to_anti_rug_evidence(result.value.to_observation())

    assert "STATIC_SCANNER_FIELDS_UNKNOWN" in result.value.reason_codes
    assert evidence.mint_freeze_or_sell_restriction is None
    assert evidence.unsafe_holder_or_creator_control is None
    assert evidence.evidence_complete is False
