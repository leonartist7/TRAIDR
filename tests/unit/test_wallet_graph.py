from onchain.wallet_graph import build_wallet_graph


def fixture_edges() -> list[dict[str, object]]:
    return [
        {"from_wallet": "funder", "to_wallet": "early_a", "amount_usd": "10", "tx_index": 1},
        {"from_wallet": "funder", "to_wallet": "early_b", "amount_usd": "11", "tx_index": 2},
        {"from_wallet": "early_a", "to_wallet": "loop_b", "amount_usd": "2", "tx_index": 3},
        {"from_wallet": "loop_b", "to_wallet": "early_a", "amount_usd": "1", "tx_index": 4},
    ]


def test_build_wallet_graph_from_fixture_edges() -> None:
    result = build_wallet_graph(fixture_edges(), early_buyer_wallets={"early_a", "early_b"})

    assert result.ok is True
    assert result.value is not None
    assert set(result.value.graph.nodes) == {"funder", "early_a", "early_b", "loop_b"}
    assert result.value.graph.number_of_edges() == 4
    assert result.value.evidence_complete is True


def test_wallet_graph_detects_shared_funder_and_early_buyer_clusters() -> None:
    result = build_wallet_graph(fixture_edges(), early_buyer_wallets={"early_a", "early_b"})
    assert result.value is not None

    assert result.value.shared_funder_clusters[0].anchor_wallet == "funder"
    assert result.value.shared_funder_clusters[0].wallets == ("early_a", "early_b")
    assert result.value.early_buyer_clusters[0].reason_codes == (
        "REPEATED_EARLY_BUYER_CLUSTER",
    )


def test_wallet_graph_detects_cyclic_transfer_loops() -> None:
    result = build_wallet_graph(fixture_edges(), early_buyer_wallets={"early_a", "early_b"})
    assert result.value is not None

    assert result.value.cyclic_transfer_loops == (("early_a", "loop_b"),)


def test_unknown_or_malformed_wallet_data_is_insufficient_not_bullish() -> None:
    unknown = build_wallet_graph(None)
    malformed = build_wallet_graph([{"from_wallet": "same", "to_wallet": "same"}])

    assert unknown.ok is False
    assert unknown.reason_codes == ("WALLET_GRAPH_EDGES_UNKNOWN",)
    assert malformed.ok is False
    assert malformed.reason_codes == ("WALLET_GRAPH_EDGE_MALFORMED",)
