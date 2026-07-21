from datetime import UTC, datetime, timedelta
from decimal import Decimal

from execution.paper_futures import PaperFuturesSimulator, PaperPositionStatus
from execution.portfolio_stress import assess_portfolio_stress
from intelligence.production_models import ProbabilityState, SignalDecision, SignalDirection


NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)


def test_partial_fill_funding_idempotency_trailing_expiry_and_reconciliation() -> None:
    simulator = PaperFuturesSimulator()
    opened = simulator.open_from_signal(
        _signal(), mark_price=Decimal("100"), risk_approved=True, market_data_fresh=True,
        depth_available=True, manual_or_auto_paper_enabled=True,
        available_depth_notional_usd=Decimal("5"), latency_ms=500, now=NOW,
    )
    assert opened.ok and opened.value is not None
    order, fill, position = opened.value
    assert order.status == "PARTIAL"
    assert fill.notional_usd == Decimal("5.00000000")
    assert fill.slippage_bps > simulator.limits.default_slippage_bps

    funding_time = NOW + timedelta(hours=8)
    assert simulator.apply_funding(position.instrument_id, Decimal("0.001"), funding_time=funding_time).ok
    duplicate = simulator.apply_funding(position.instrument_id, Decimal("0.001"), funding_time=funding_time)
    assert duplicate.status == "HOLD"
    assert simulator.enable_trailing_stop(position.instrument_id, distance_fraction=Decimal("0.01")).ok
    expired = simulator.process_price(position.instrument_id, Decimal("101"), now=position.expires_at)
    assert expired.ok and expired.value is not None
    assert expired.value.status is PaperPositionStatus.CLOSED
    assert abs(simulator.reconcile()) <= simulator.limits.accounting_tolerance_usd


def test_portfolio_stress_rejects_concentrated_correlated_loss() -> None:
    simulator = PaperFuturesSimulator()
    simulator.open_from_signal(
        _signal(), mark_price=Decimal("100"), risk_approved=True, market_data_fresh=True,
        depth_available=True, manual_or_auto_paper_enabled=True, now=NOW,
    )
    snapshot = simulator.snapshot(NOW)
    history = [float(index) for index in range(20)]
    stress = assess_portfolio_stress(
        snapshot,
        {"bitunix:BTCUSDT": history},
        maximum_stressed_loss_fraction=Decimal("0.001"),
    )

    assert not stress.approved
    assert "PAPER_SIMULTANEOUS_LOSS_LIMIT" in stress.reason_codes


def _signal() -> SignalDecision:
    return SignalDecision(
        signal_id="signal-long", idempotency_key="signal:long", instrument_id="bitunix:BTCUSDT",
        direction=SignalDirection.LONG, horizon="15m", setup_type="TEST", generated_at=NOW,
        expires_at=NOW + timedelta(minutes=15), entry_low=Decimal("99"), entry_high=Decimal("101"),
        invalidation=Decimal("98"), stop=Decimal("98"), targets=(Decimal("104"), Decimal("106")),
        expected_return_pct=3.0, risk_reward=2.0, opportunity_score=75, risk_score=25,
        data_coverage=0.9, probability_state=ProbabilityState.UNCALIBRATED,
        model_version="test", liquidity_grade="A", risk_grade="LOW",
        reasons=("test",), evidence_ids=("evidence",),
    )
