from datetime import datetime, timedelta, timezone
from decimal import Decimal

from risk.engine import RiskEngine
from risk.models import (
    AntiRugEvidence,
    IntentAction,
    MarketDataState,
    PortfolioState,
    RiskOutcome,
    RiskRequest,
    SignalConfidence,
)

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def safe_request(**overrides: object) -> RiskRequest:
    values: dict[str, object] = {
        "action": IntentAction.BUY,
        "confidence": SignalConfidence.HIGH,
        "requested_notional_usd": Decimal("10"),
        "portfolio": PortfolioState(
            bankroll_usd=Decimal("50"),
            current_exposure_usd=Decimal("20"),
            open_positions=2,
            daily_loss_usd=Decimal("0"),
        ),
        "market_data": MarketDataState(
            observed_at=NOW - timedelta(minutes=1),
            provenance_known=True,
        ),
        "anti_rug": AntiRugEvidence(
            liquidity_accessible=True,
            liquidity_meets_floor=True,
            liquidity_status_known=True,
            mint_freeze_or_sell_restriction=False,
            unsafe_holder_or_creator_control=False,
            honeypot_tax_route_or_sellability_issue=False,
            identity_ambiguous=False,
            evidence_complete=True,
        ),
        "mode": "simulation",
        "now": NOW,
    }
    values.update(overrides)
    return RiskRequest(**values)


def test_engine_approves_only_safe_simulation_buy() -> None:
    decision = RiskEngine().evaluate(safe_request())

    assert decision.outcome is RiskOutcome.APPROVED
    assert decision.approved is True
    assert decision.approved_notional_usd == Decimal("10")


def test_anti_rug_hard_fail_overrides_high_confidence_signal() -> None:
    unsafe_evidence = safe_request().anti_rug
    decision = RiskEngine().evaluate(
        safe_request(
            anti_rug=AntiRugEvidence(
                **{
                    **unsafe_evidence.__dict__,
                    "identity_ambiguous": True,
                }
            )
        )
    )

    assert decision.outcome is RiskOutcome.HOLD
    assert decision.reason_codes == ("ANTI_RUG_IDENTITY_AMBIGUOUS",)


def test_missing_or_stale_market_data_is_insufficient() -> None:
    missing = RiskEngine().evaluate(
        safe_request(market_data=MarketDataState(observed_at=None, provenance_known=True))
    )
    stale = RiskEngine().evaluate(
        safe_request(
            market_data=MarketDataState(
                observed_at=NOW - timedelta(minutes=10),
                provenance_known=True,
            )
        )
    )

    assert missing.outcome is RiskOutcome.INSUFFICIENT_DATA
    assert missing.reason_codes == ("TIMESTAMP_MISSING",)
    assert stale.outcome is RiskOutcome.INSUFFICIENT_DATA
    assert stale.reason_codes == ("TIMESTAMP_STALE",)


def test_low_confidence_and_live_mode_hold() -> None:
    low_confidence = RiskEngine().evaluate(
        safe_request(confidence=SignalConfidence.LOW)
    )
    non_simulation = RiskEngine().evaluate(safe_request(mode="live"))

    assert low_confidence.outcome is RiskOutcome.HOLD
    assert low_confidence.reason_codes == ("CONFIDENCE_TOO_LOW",)
    assert non_simulation.outcome is RiskOutcome.HOLD
    assert non_simulation.reason_codes == ("MODE_NOT_SIMULATION",)


def test_limit_breaches_hold_before_paper_execution() -> None:
    oversized = RiskEngine().evaluate(
        safe_request(requested_notional_usd=Decimal("10.01"))
    )
    daily_loss_halt = RiskEngine().evaluate(
        safe_request(
            portfolio=PortfolioState(
                bankroll_usd=Decimal("50"),
                current_exposure_usd=Decimal("20"),
                open_positions=2,
                daily_loss_usd=Decimal("5"),
            )
        )
    )
    full_positions = RiskEngine().evaluate(
        safe_request(
            portfolio=PortfolioState(
                bankroll_usd=Decimal("50"),
                current_exposure_usd=Decimal("20"),
                open_positions=3,
                daily_loss_usd=Decimal("0"),
            )
        )
    )

    assert oversized.outcome is RiskOutcome.HOLD
    assert oversized.reason_codes == (
        "MAX_POSITION_NOTIONAL_EXCEEDED",
        "MAX_TOTAL_EXPOSURE_EXCEEDED",
    )
    assert daily_loss_halt.reason_codes == ("DAILY_LOSS_HALT",)
    assert full_positions.reason_codes == ("MAX_OPEN_POSITIONS_REACHED",)

