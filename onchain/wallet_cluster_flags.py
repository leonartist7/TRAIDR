"""Wallet cluster risk flags for anti-rug research."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from onchain.contracts import OnchainSafetyObservation
from utils.results import Result


@dataclass(frozen=True)
class WalletClusterFlagAnalysis:
    """Research signal for clustered wallet control."""

    largest_cluster_fraction: Decimal
    unsafe_holder_or_creator_control: bool
    reason_codes: tuple[str, ...]

    def to_observation(self) -> OnchainSafetyObservation:
        return OnchainSafetyObservation(
            unsafe_holder_or_creator_control=self.unsafe_holder_or_creator_control,
            evidence_complete=True,
        )


def analyze_wallet_clusters(
    cluster_supply_fractions: Iterable[Decimal] | None,
    *,
    hard_fail_fraction: Decimal = Decimal("0.40"),
) -> Result[WalletClusterFlagAnalysis]:
    """Flag likely coordinated wallet clusters without treating unknowns as safe."""

    if cluster_supply_fractions is None:
        return Result.insufficient_data("WALLET_CLUSTERS_UNKNOWN")
    clusters = tuple(cluster_supply_fractions)
    if not clusters:
        return Result.insufficient_data("WALLET_CLUSTERS_UNKNOWN")
    if any(value < Decimal("0") or value > Decimal("1") for value in clusters):
        return Result.insufficient_data("WALLET_CLUSTER_DATA_MALFORMED")

    largest = max(clusters)
    unsafe = largest >= hard_fail_fraction
    return Result.success(
        WalletClusterFlagAnalysis(
            largest_cluster_fraction=largest,
            unsafe_holder_or_creator_control=unsafe,
            reason_codes=(
                ("WALLET_CLUSTER_CONTROL_HARD_FAIL",)
                if unsafe
                else ("WALLET_CLUSTER_CONTROL_NOT_DETECTED",)
            ),
        )
    )
