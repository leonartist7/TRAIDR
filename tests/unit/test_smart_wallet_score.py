from decimal import Decimal

from onchain.smart_wallet_score import score_smart_wallet
from onchain.wallet_cluster_scorer import WalletClusterScore
from onchain.wallet_profiles import build_wallet_profile


def test_smart_wallet_score_requires_complete_evidence() -> None:
    score = score_smart_wallet(build_wallet_profile(None))

    assert score.smart_wallet_score is None
    assert score.evidence_complete is False
    assert "SMART_WALLET_EVIDENCE_INCOMPLETE" in score.reason_codes


def test_smart_wallet_score_is_separate_from_cluster_risk() -> None:
    profile = build_wallet_profile(
        {
            "wallet": "wallet-a",
            "developer_link_risk": False,
            "trades": [
                {"early_entry": True, "outcome": "win", "avoided_rug": True},
                {"early_entry": True, "outcome": "win", "avoided_rug": True},
            ],
        }
    )
    cluster = WalletClusterScore(
        wallet_cluster_risk_score=Decimal("20"),
        smart_wallet_candidate_score=None,
        evidence_complete=True,
        reason_codes=("SHARED_FUNDER_RISK",),
    )

    score = score_smart_wallet(profile, cluster)

    assert score.evidence_complete is True
    assert score.smart_wallet_score is not None
    assert score.smart_wallet_score > Decimal("0")
    assert score.wallet_cluster_risk_score == Decimal("20")
    assert "SHARED_FUNDER_RISK" in score.reason_codes
    assert score.to_dict()["can_execute_trades"] is False


def test_developer_link_risk_penalizes_smart_wallet_score() -> None:
    safe_profile = build_wallet_profile(
        {
            "wallet": "wallet-a",
            "developer_link_risk": False,
            "trades": [{"early_entry": True, "outcome": "win", "avoided_rug": True}],
        }
    )
    risky_profile = build_wallet_profile(
        {
            "wallet": "wallet-a",
            "developer_link_risk": True,
            "trades": [{"early_entry": True, "outcome": "win", "avoided_rug": True}],
        }
    )

    assert score_smart_wallet(risky_profile).smart_wallet_score < score_smart_wallet(safe_profile).smart_wallet_score
