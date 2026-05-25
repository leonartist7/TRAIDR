from onchain.wallet_profiles import build_wallet_profile


def test_wallet_profile_is_complete_when_all_evidence_exists() -> None:
    profile = build_wallet_profile(
        {
            "wallet": "wallet-a",
            "developer_link_risk": False,
            "trades": [
                {"early_entry": True, "outcome": "win", "avoided_rug": True},
                {"early_entry": False, "outcome": "loss", "rugged": True},
            ],
        }
    )

    assert profile.evidence_complete is True
    assert "WALLET_PROFILE_COMPLETE" in profile.reason_codes
    assert profile.to_dict()["can_execute_trades"] is False


def test_wallet_profile_unknown_history_is_incomplete() -> None:
    profile = build_wallet_profile(None)

    assert profile.evidence_complete is False
    assert "WALLET_PROFILE_INCOMPLETE" in profile.reason_codes
