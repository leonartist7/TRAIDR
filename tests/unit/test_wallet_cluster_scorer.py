from decimal import Decimal

from onchain.wallet_cluster_scorer import score_wallet_clusters
from onchain.wallet_graph import build_wallet_graph


def risky_edges() -> list[dict[str, object]]:
    return [
        {"from_wallet": "funder", "to_wallet": "early_a", "amount_usd": "10"},
        {"from_wallet": "funder", "to_wallet": "early_b", "amount_usd": "11"},
        {"from_wallet": "early_a", "to_wallet": "loop_b", "amount_usd": "2"},
        {"from_wallet": "loop_b", "to_wallet": "early_a", "amount_usd": "1"},
    ]


def test_wallet_cluster_scorer_outputs_risk_score() -> None:
    graph_result = build_wallet_graph(risky_edges(), early_buyer_wallets={"early_a", "early_b"})
    assert graph_result.value is not None

    score = score_wallet_clusters(graph_result.value)

    assert score.ok is True
    assert score.value is not None
    assert score.value.wallet_cluster_risk_score == Decimal("90")
    assert score.value.reason_codes[:3] == (
        "SHARED_FUNDER_RISK",
        "EARLY_BUYER_CLUSTER_RISK",
        "CYCLIC_TRANSFER_LOOP_RISK",
    )


def test_smart_wallet_candidate_score_only_when_evidence_complete() -> None:
    incomplete_graph = build_wallet_graph(
        [{"from_wallet": "wallet_a", "to_wallet": "wallet_b", "amount_usd": "1"}]
    )
    complete_graph = build_wallet_graph(
        [{"from_wallet": "wallet_a", "to_wallet": "early_a", "amount_usd": "1"}],
        early_buyer_wallets={"early_a"},
    )
    assert incomplete_graph.value is not None
    assert complete_graph.value is not None

    incomplete = score_wallet_clusters(incomplete_graph.value)
    complete = score_wallet_clusters(complete_graph.value)

    assert incomplete.value is not None
    assert complete.value is not None
    assert incomplete.value.smart_wallet_candidate_score is None
    assert incomplete.value.reason_codes[-1] == "SMART_WALLET_EVIDENCE_INCOMPLETE"
    assert complete.value.smart_wallet_candidate_score == Decimal("20")
    assert complete.value.reason_codes[-1] == "SMART_WALLET_EVIDENCE_COMPLETE"


def test_unknown_wallet_analysis_is_insufficient_not_bullish() -> None:
    score = score_wallet_clusters(None)

    assert score.ok is False
    assert score.reason_codes == ("WALLET_GRAPH_ANALYSIS_MISSING",)
