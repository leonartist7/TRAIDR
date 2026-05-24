"""Fixture-only wallet graph construction using NetworkX."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import networkx as nx

from utils.results import Result


@dataclass(frozen=True)
class WalletCluster:
    """Detected wallet cluster around one coordinating wallet."""

    cluster_type: str
    anchor_wallet: str
    wallets: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class WalletGraphAnalysis:
    """Wallet graph plus deterministic cluster signals from fixture data."""

    graph: nx.MultiDiGraph
    shared_funder_clusters: tuple[WalletCluster, ...]
    early_buyer_clusters: tuple[WalletCluster, ...]
    cyclic_transfer_loops: tuple[tuple[str, ...], ...]
    early_buyer_wallets: frozenset[str]
    evidence_complete: bool


def build_wallet_graph(
    edges: Iterable[Mapping[str, Any]] | None,
    *,
    early_buyer_wallets: Iterable[str] | None = None,
    min_shared_funded_wallets: int = 2,
    min_repeated_early_buyer_funder: int = 2,
) -> Result[WalletGraphAnalysis]:
    """Build a fixture transaction graph and detect simple cluster patterns."""

    if edges is None:
        return Result.insufficient_data("WALLET_GRAPH_EDGES_UNKNOWN")
    edge_rows = tuple(edges)
    if not edge_rows:
        return Result.insufficient_data("WALLET_GRAPH_EDGES_MISSING")
    if min_shared_funded_wallets < 2 or min_repeated_early_buyer_funder < 2:
        raise ValueError("wallet graph cluster thresholds must be at least 2")

    graph = nx.MultiDiGraph()
    for index, raw in enumerate(edge_rows):
        edge = _normalize_edge(raw, index)
        if edge is None:
            return Result.insufficient_data("WALLET_GRAPH_EDGE_MALFORMED")
        from_wallet, to_wallet, amount_usd, tx_index = edge
        graph.add_edge(
            from_wallet,
            to_wallet,
            amount_usd=amount_usd,
            tx_index=tx_index,
        )

    early_buyers = _normalize_wallet_set(early_buyer_wallets)
    if early_buyer_wallets is not None and not early_buyers:
        return Result.insufficient_data("EARLY_BUYER_WALLETS_MALFORMED")

    simple_graph = nx.DiGraph()
    simple_graph.add_edges_from((source, target) for source, target in graph.edges())
    return Result.success(
        WalletGraphAnalysis(
            graph=graph,
            shared_funder_clusters=_shared_funder_clusters(
                simple_graph,
                min_shared_funded_wallets=min_shared_funded_wallets,
            ),
            early_buyer_clusters=_early_buyer_clusters(
                simple_graph,
                early_buyers=early_buyers,
                min_repeated_early_buyer_funder=min_repeated_early_buyer_funder,
            ),
            cyclic_transfer_loops=_cyclic_transfer_loops(simple_graph),
            early_buyer_wallets=frozenset(early_buyers),
            evidence_complete=early_buyer_wallets is not None,
        )
    )


def _normalize_edge(
    raw: Mapping[str, Any],
    fallback_index: int,
) -> tuple[str, str, Decimal, int] | None:
    try:
        from_wallet = str(raw["from_wallet"]).strip()
        to_wallet = str(raw["to_wallet"]).strip()
        amount_usd = Decimal(str(raw.get("amount_usd", "0")))
        tx_index = int(raw.get("tx_index", fallback_index))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    if not from_wallet or not to_wallet or from_wallet == to_wallet:
        return None
    if amount_usd < Decimal("0") or tx_index < 0:
        return None
    return from_wallet, to_wallet, amount_usd, tx_index


def _normalize_wallet_set(wallets: Iterable[str] | None) -> set[str]:
    if wallets is None:
        return set()
    return {str(wallet).strip() for wallet in wallets if str(wallet).strip()}


def _shared_funder_clusters(
    graph: nx.DiGraph,
    *,
    min_shared_funded_wallets: int,
) -> tuple[WalletCluster, ...]:
    clusters: list[WalletCluster] = []
    for wallet in sorted(graph.nodes):
        recipients = tuple(sorted(graph.successors(wallet)))
        if len(recipients) >= min_shared_funded_wallets:
            clusters.append(
                WalletCluster(
                    cluster_type="shared_funder",
                    anchor_wallet=wallet,
                    wallets=recipients,
                    reason_codes=("SHARED_FUNDER_CLUSTER",),
                )
            )
    return tuple(clusters)


def _early_buyer_clusters(
    graph: nx.DiGraph,
    *,
    early_buyers: set[str],
    min_repeated_early_buyer_funder: int,
) -> tuple[WalletCluster, ...]:
    if not early_buyers:
        return ()
    clusters: list[WalletCluster] = []
    for wallet in sorted(graph.nodes):
        recipients = tuple(sorted(set(graph.successors(wallet)) & early_buyers))
        if len(recipients) >= min_repeated_early_buyer_funder:
            clusters.append(
                WalletCluster(
                    cluster_type="early_buyer_funder",
                    anchor_wallet=wallet,
                    wallets=recipients,
                    reason_codes=("REPEATED_EARLY_BUYER_CLUSTER",),
                )
            )
    return tuple(clusters)


def _cyclic_transfer_loops(graph: nx.DiGraph) -> tuple[tuple[str, ...], ...]:
    normalized = {_canonical_cycle(tuple(cycle)) for cycle in nx.simple_cycles(graph)}
    return tuple(sorted(normalized))


def _canonical_cycle(cycle: tuple[str, ...]) -> tuple[str, ...]:
    rotations = [cycle[index:] + cycle[:index] for index in range(len(cycle))]
    return min(rotations)
