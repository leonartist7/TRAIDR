from datetime import datetime, timezone
from decimal import Decimal

from onchain.lp_lock_analysis import analyze_lp_lock
from onchain.rug_observations import to_anti_rug_evidence
from risk.anti_rug import assess_anti_rug

NOW = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)


def test_unknown_lp_lock_status_is_insufficient_data() -> None:
    result = analyze_lp_lock(
        lock_known=None,
        unlocks_at=None,
        locked_liquidity_usd=None,
        minimum_locked_liquidity_usd=Decimal("1000"),
        now=NOW,
    )

    assert result.ok is False
    assert result.reason_codes == ("LP_LOCK_STATUS_UNKNOWN",)


def test_absent_lp_lock_maps_to_anti_rug_hard_fail() -> None:
    result = analyze_lp_lock(
        lock_known=False,
        unlocks_at=None,
        locked_liquidity_usd=Decimal("0"),
        minimum_locked_liquidity_usd=Decimal("1000"),
        now=NOW,
    )
    assert result.value is not None
    evidence = to_anti_rug_evidence(result.value.to_observation())
    assessment = assess_anti_rug(evidence)

    assert result.value.reason_codes == ("LP_LOCK_ABSENT",)
    assert assessment.hard_fail_reasons == (
        "ANTI_RUG_LIQUIDITY_INACCESSIBLE",
        "ANTI_RUG_LIQUIDITY_BELOW_FLOOR",
    )


def test_confirmed_lp_lock_does_not_make_unknown_fields_bullish() -> None:
    result = analyze_lp_lock(
        lock_known=True,
        unlocks_at="2026-06-24T12:00:00+00:00",
        locked_liquidity_usd=Decimal("5000"),
        minimum_locked_liquidity_usd=Decimal("1000"),
        now=NOW,
    )
    assert result.value is not None
    evidence = to_anti_rug_evidence(result.value.to_observation())

    assert result.value.reason_codes == ("LP_LOCK_CONFIRMED",)
    assert evidence.liquidity_accessible is True
    assert evidence.liquidity_meets_floor is True
    assert evidence.mint_freeze_or_sell_restriction is None
