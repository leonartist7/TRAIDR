from onchain.contracts import OnchainSafetyObservation
from onchain.goat_adapter import GoatSafetyAdapter
from onchain.rug_observations import to_anti_rug_evidence


def test_unknown_onchain_fields_remain_unknown_in_risk_evidence() -> None:
    evidence = to_anti_rug_evidence(OnchainSafetyObservation(liquidity_accessible=True))

    assert evidence.liquidity_accessible is True
    assert evidence.liquidity_meets_floor is None
    assert evidence.honeypot_tax_route_or_sellability_issue is None


def test_goat_wrapper_is_mocked_and_preserves_unknown_fields() -> None:
    absent = GoatSafetyAdapter().fetch_observation("token")
    mocked = GoatSafetyAdapter(
        lambda _token: {"liquidity_accessible": True, "identity_ambiguous": False}
    ).fetch_observation("token")

    assert absent.reason_codes == ("GOAT_TRANSPORT_UNAVAILABLE",)
    assert mocked.ok is True
    assert mocked.value is not None
    assert mocked.value.liquidity_accessible is True
    assert mocked.value.evidence_complete is None

