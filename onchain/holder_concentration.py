"""Holder concentration research helpers for anti-rug evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from onchain.contracts import OnchainSafetyObservation
from utils.results import Result

DEFAULT_TOP_HOLDER_HARD_FAIL = Decimal("0.35")
DEFAULT_TOP_5_HOLDER_HARD_FAIL = Decimal("0.70")


@dataclass(frozen=True)
class HolderConcentrationAnalysis:
    """Deterministic concentration signal for top holders."""

    top_holder_fraction: Decimal
    top_5_fraction: Decimal
    unsafe_holder_or_creator_control: bool
    reason_codes: tuple[str, ...]

    def to_observation(self) -> OnchainSafetyObservation:
        return OnchainSafetyObservation(
            unsafe_holder_or_creator_control=self.unsafe_holder_or_creator_control,
            evidence_complete=True,
        )


def analyze_holder_concentration(
    holder_fractions: Iterable[Decimal] | None,
    *,
    top_holder_hard_fail: Decimal = DEFAULT_TOP_HOLDER_HARD_FAIL,
    top_5_hard_fail: Decimal = DEFAULT_TOP_5_HOLDER_HARD_FAIL,
) -> Result[HolderConcentrationAnalysis]:
    """Flag high holder concentration as a hard-fail anti-rug signal."""

    if holder_fractions is None:
        return Result.insufficient_data("HOLDER_DISTRIBUTION_UNKNOWN")
    fractions = tuple(holder_fractions)
    if not fractions:
        return Result.insufficient_data("HOLDER_DISTRIBUTION_UNKNOWN")
    if any(value < Decimal("0") or value > Decimal("1") for value in fractions):
        return Result.insufficient_data("HOLDER_DISTRIBUTION_MALFORMED")

    sorted_fractions = tuple(sorted(fractions, reverse=True))
    top_holder = sorted_fractions[0]
    top_5 = sum(sorted_fractions[:5], Decimal("0"))
    reasons: list[str] = []
    if top_holder >= top_holder_hard_fail:
        reasons.append("TOP_HOLDER_CONCENTRATION_HARD_FAIL")
    if top_5 >= top_5_hard_fail:
        reasons.append("TOP_5_HOLDER_CONCENTRATION_HARD_FAIL")
    if not reasons:
        reasons.append("HOLDER_CONCENTRATION_ACCEPTABLE")

    return Result.success(
        HolderConcentrationAnalysis(
            top_holder_fraction=top_holder,
            top_5_fraction=top_5,
            unsafe_holder_or_creator_control=any(
                reason.endswith("HARD_FAIL") for reason in reasons
            ),
            reason_codes=tuple(reasons),
        )
    )
