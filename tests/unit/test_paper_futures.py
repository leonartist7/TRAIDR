from datetime import UTC, datetime, timedelta
from decimal import Decimal

from execution.paper_futures import PaperFuturesSimulator, PaperPositionStatus
from intelligence.production_models import ProbabilityState, SignalDecision, SignalDirection
from risk.production_gate import assess_paper_signal


NOW = datetime(2026, 7, 20, 12, tzinfo=UTC)


def test_paper_futures_opens_long_and_rejects_averaging() -> None:
    simulator = PaperFuturesSimulator()
    signal = _signal(SignalDirection.LONG)

    opened = simulator.open_from_signal(
        signal,
        mark_price=Decimal("100"),
        risk_approved=True,
        market_data_fresh=True,
        depth_available=True,
        manual_or_auto_paper_enabled=True,
        now=NOW,
    )
    duplicate = simulator.open_from_signal(
        signal,
        mark_price=Decimal("100"),
        risk_approved=True,
        market_data_fresh=True,
        depth_available=True,
        manual_or_auto_paper_enabled=True,
        now=NOW,
    )

    assert opened.ok and opened.value is not None
    order, fill, position = opened.value
    assert order.can_execute_trades is False
    assert fill.fee_usd > 0
    assert position.status is PaperPositionStatus.OPEN
    assert position.liquidation_price < position.entry_price
    assert duplicate.status == "HOLD"


def test_paper_futures_short_profit_and_funding_accounting() -> None:
    simulator = PaperFuturesSimulator()
    signal = _signal(SignalDirection.SHORT)
    opened = simulator.open_from_signal(
        signal,
        mark_price=Decimal("100"),
        risk_approved=True,
        market_data_fresh=True,
        depth_available=True,
        manual_or_auto_paper_enabled=True,
        now=NOW,
    )
    assert opened.ok and opened.value is not None
    position = opened.value[2]

    funded = simulator.apply_funding(signal.instrument_id, Decimal("0.001"))
    closed = simulator.close(
        signal.instrument_id,
        exit_price=Decimal("95"),
        now=NOW + timedelta(minutes=10),
    )

    assert funded.ok
    assert closed.ok and closed.value is not None
    assert closed.value.status is PaperPositionStatus.CLOSED
    assert closed.value.realized_pnl_usd > 0
    assert position.liquidation_price > position.entry_price


def test_paper_futures_fails_closed_on_stale_data() -> None:
    result = PaperFuturesSimulator().open_from_signal(
        _signal(SignalDirection.LONG),
        mark_price=Decimal("100"),
        risk_approved=True,
        market_data_fresh=False,
        depth_available=True,
        manual_or_auto_paper_enabled=True,
        now=NOW,
    )
    assert result.status == "INSUFFICIENT_DATA"
    assert result.value is None


def test_deterministic_gate_and_gap_stop_precede_paper_action() -> None:
    simulator = PaperFuturesSimulator()
    signal = _signal(SignalDirection.LONG)
    assessment = assess_paper_signal(
        signal,
        simulator.snapshot(NOW),
        limits=simulator.limits,
        market_fresh=True,
        depth_available=True,
        mark_index_available=True,
        now=NOW,
    )
    assert assessment.outcome == "APPROVED_PAPER"

    opened = simulator.open_from_signal(
        signal,
        mark_price=Decimal("100"),
        risk_approved=True,
        market_data_fresh=True,
        depth_available=True,
        manual_or_auto_paper_enabled=True,
        now=NOW,
    )
    assert opened.ok
    stopped = simulator.process_price(
        signal.instrument_id,
        Decimal("97"),
        now=NOW + timedelta(minutes=1),
    )
    assert stopped.ok and stopped.value is not None
    assert stopped.value.status is PaperPositionStatus.CLOSED
    assert stopped.value.realized_pnl_usd < 0


def test_paper_portfolio_restores_open_positions_and_processed_keys() -> None:
    simulator = PaperFuturesSimulator()
    signal = _signal(SignalDirection.SHORT)
    opened = simulator.open_from_signal(
        signal,
        mark_price=Decimal("100"),
        risk_approved=True,
        market_data_fresh=True,
        depth_available=True,
        manual_or_auto_paper_enabled=True,
        now=NOW,
    )
    assert opened.ok
    snapshot = simulator.snapshot(NOW)
    position = opened.value[2]  # type: ignore[index]
    position_payload = {
        **position.__dict__,
        "direction": position.direction.value,
        "status": position.status.value,
        "opened_at": position.opened_at.isoformat(),
        "updated_at": position.updated_at.isoformat(),
    }
    payload = {
        "cash_usd": str(snapshot.cash_usd),
        "realized_pnl_usd": str(snapshot.realized_pnl_usd),
        "daily_pnl_usd": str(snapshot.daily_pnl_usd),
        "open_positions": [position_payload],
    }
    restored = PaperFuturesSimulator.from_persisted_portfolio(
        payload,
        processed_idempotency_keys=(signal.idempotency_key,),
    )
    assert restored.open_positions()[0].direction is SignalDirection.SHORT
    assert signal.idempotency_key in restored.processed_idempotency_keys


def _signal(direction: SignalDirection) -> SignalDecision:
    if direction is SignalDirection.LONG:
        stop, targets = Decimal("98"), (Decimal("104"), Decimal("106"))
    else:
        stop, targets = Decimal("102"), (Decimal("96"), Decimal("94"))
    return SignalDecision(
        signal_id=f"signal-{direction.value.lower()}",
        idempotency_key=f"signal:{direction.value.lower()}",
        instrument_id="bitunix:BTCUSDT",
        direction=direction,
        horizon="15m",
        setup_type="TEST_SETUP",
        generated_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
        entry_low=Decimal("99.8"),
        entry_high=Decimal("100.2"),
        invalidation=stop,
        stop=stop,
        targets=targets,
        expected_return_pct=Decimal("3.8"),
        risk_reward=2.0,
        opportunity_score=75,
        risk_score=25,
        data_coverage=0.9,
        probability_state=ProbabilityState.UNCALIBRATED,
        calibration_sample_size=0,
        model_version="test-v1",
        liquidity_grade="A",
        risk_grade="LOW",
        reasons=("test evidence",),
        evidence_ids=("evidence-test",),
    )
