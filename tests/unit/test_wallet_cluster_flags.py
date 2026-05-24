from decimal import Decimal

from onchain.rug_observations import to_anti_rug_evidence
from onchain.wallet_cluster_flags import analyze_wallet_clusters
from risk.anti_rug import assess_anti_rug


def test_unknown_wallet_clusters_are_insufficient_data() -> None:
    result = analyze_wallet_clusters(None)

    assert result.ok is False
    assert result.reason_codes == ("WALLET_CLUSTERS_UNKNOWN",)


def test_wallet_cluster_control_maps_to_holder_control_hard_fail() -> None:
    result = analyze_wallet_clusters([Decimal("0.45"), Decimal("0.10")])
    assert result.value is not None
    evidence = to_anti_rug_evidence(result.value.to_observation())
    assessment = assess_anti_rug(evidence)

    assert result.value.reason_codes == ("WALLET_CLUSTER_CONTROL_HARD_FAIL",)
    assert result.value.unsafe_holder_or_creator_control is True
    assert assessment.hard_fail_reasons == ("ANTI_RUG_HOLDER_OR_CREATOR_CONTROL",)


def test_wallet_cluster_clear_preserves_other_unknown_safety_fields() -> None:
    result = analyze_wallet_clusters([Decimal("0.20"), Decimal("0.15")])
    assert result.value is not None
    evidence = to_anti_rug_evidence(result.value.to_observation())

    assert result.value.reason_codes == ("WALLET_CLUSTER_CONTROL_NOT_DETECTED",)
    assert evidence.unsafe_holder_or_creator_control is False
    assert evidence.liquidity_status_known is None
