"""LP lock research helpers that fail closed on unknown lock state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from onchain.contracts import OnchainSafetyObservation
from utils.clocks import parse_utc_timestamp
from utils.results import Result


@dataclass(frozen=True)
class LpLockAnalysis:
    """Normalized LP lock research signal."""

    liquidity_status_known: bool
    liquidity_accessible: bool
    liquidity_meets_floor: bool
    locked_liquidity_usd: Decimal | None
    reason_codes: tuple[str, ...]

    def to_observation(self) -> OnchainSafetyObservation:
        return OnchainSafetyObservation(
            liquidity_accessible=self.liquidity_accessible,
            liquidity_meets_floor=self.liquidity_meets_floor,
            liquidity_status_known=self.liquidity_status_known,
            evidence_complete=self.liquidity_status_known,
        )


def analyze_lp_lock(
    *,
    lock_known: bool | None,
    unlocks_at: datetime | str | None,
    locked_liquidity_usd: Decimal | None,
    minimum_locked_liquidity_usd: Decimal,
    now: datetime | str | None,
) -> Result[LpLockAnalysis]:
    """Return an unsafe/insufficient LP lock result instead of assuming safety."""

    if minimum_locked_liquidity_usd <= Decimal("0"):
        raise ValueError("minimum locked liquidity must be positive")
    if lock_known is None:
        return Result.insufficient_data("LP_LOCK_STATUS_UNKNOWN")
    if lock_known is False:
        return Result.success(
            LpLockAnalysis(
                liquidity_status_known=True,
                liquidity_accessible=False,
                liquidity_meets_floor=False,
                locked_liquidity_usd=locked_liquidity_usd,
                reason_codes=("LP_LOCK_ABSENT",),
            )
        )
    if locked_liquidity_usd is None or locked_liquidity_usd < Decimal("0"):
        return Result.insufficient_data("LP_LOCK_LIQUIDITY_UNKNOWN")

    unlock_result = parse_utc_timestamp(unlocks_at)
    now_result = parse_utc_timestamp(now)
    if not unlock_result.ok or unlock_result.value is None:
        return Result.insufficient_data("LP_LOCK_UNLOCK_TIME_UNKNOWN", *unlock_result.reason_codes)
    if not now_result.ok or now_result.value is None:
        return Result.insufficient_data("LP_LOCK_CHECK_TIME_UNKNOWN", *now_result.reason_codes)

    unlocked = unlock_result.value <= now_result.value
    meets_floor = locked_liquidity_usd >= minimum_locked_liquidity_usd
    reasons: list[str] = []
    if unlocked:
        reasons.append("LP_LOCK_EXPIRED")
    if not meets_floor:
        reasons.append("LP_LOCK_LIQUIDITY_BELOW_FLOOR")
    if not reasons:
        reasons.append("LP_LOCK_CONFIRMED")

    return Result.success(
        LpLockAnalysis(
            liquidity_status_known=True,
            liquidity_accessible=not unlocked,
            liquidity_meets_floor=meets_floor,
            locked_liquidity_usd=locked_liquidity_usd,
            reason_codes=tuple(reasons),
        )
    )
