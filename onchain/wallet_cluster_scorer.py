"""Score fixture wallet graph cluster risk conservatively."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from onchain.wallet_graph import WalletGraphAnalysis
from utils.results import Result


@dataclass(frozen=True)
class WalletClusterScore:
    """Deterministic wallet graph scores for anti-rug research."""

    wallet_cluster_risk_score: Decimal
    smart_wallet_candidate_score: Decimal | None
    evidence_complete: bool
    reason_codes: tuple[str, ...]


def score_wallet_clusters(
    analysis: WalletGraphAnalysis | None,
) -> Result[WalletClusterScore]:
    """Score wallet cluster risk without treating unknown data as bullish."""

    if analysis is None:
        return Result.insufficient_data("WALLET_GRAPH_ANALYSIS_MISSING")

    shared_count = len(analysis.shared_funder_clusters)
    early_count = len(analysis.early_buyer_clusters)
    cycle_count = len(analysis.cyclic_transfer_loops)
    risk_score = min(
        Decimal("100"),
        Decimal(shared_count * 25 + early_count * 30 + cycle_count * 35),
    )
    reasons: list[str] = []
    if shared_count:
        reasons.append("SHARED_FUNDER_RISK")
    if early_count:
        reasons.append("EARLY_BUYER_CLUSTER_RISK")
    if cycle_count:
        reasons.append("CYCLIC_TRANSFER_LOOP_RISK")
    if not reasons:
        reasons.append("WALLET_CLUSTER_RISK_NOT_DETECTED")

    smart_score: Decimal | None = None
    if analysis.evidence_complete:
        early_wallets_seen = len(analysis.early_buyer_wallets & set(analysis.graph.nodes))
        smart_score = max(
            Decimal("0"),
            min(Decimal("100"), Decimal(early_wallets_seen * 20) - risk_score),
        )
        reasons.append("SMART_WALLET_EVIDENCE_COMPLETE")
    else:
        reasons.append("SMART_WALLET_EVIDENCE_INCOMPLETE")

    return Result.success(
        WalletClusterScore(
            wallet_cluster_risk_score=risk_score,
            smart_wallet_candidate_score=smart_score,
            evidence_complete=analysis.evidence_complete,
            reason_codes=tuple(reasons),
        )
    )
