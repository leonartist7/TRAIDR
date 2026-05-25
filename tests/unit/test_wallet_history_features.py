from onchain.wallet_history_features import extract_wallet_history_features


def test_wallet_history_features_score_fixture_history() -> None:
    features = extract_wallet_history_features(
        {
            "wallet": "wallet-a",
            "developer_link_risk": False,
            "trades": [
                {"early_entry": True, "outcome": "win", "avoided_rug": True},
                {"early_entry": True, "outcome": "loss", "rugged": True},
                {"early_entry": False, "outcome": "win"},
            ],
        }
    )

    assert features.wallet == "wallet-a"
    assert features.early_entry_count == 2
    assert features.win_loss_ratio == 2
    assert features.rug_avoidance_rate == 0.5
    assert features.developer_link_risk is False
    assert features.to_dict()["can_execute_trades"] is False


def test_unknown_wallet_history_is_not_bullish() -> None:
    features = extract_wallet_history_features(None)

    assert features.early_entry_count is None
    assert features.win_loss_ratio is None
    assert features.rug_avoidance_rate is None
    assert "WALLET_HISTORY_UNKNOWN" in features.reason_codes
