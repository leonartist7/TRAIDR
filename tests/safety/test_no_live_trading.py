import json
from decimal import Decimal

from agents.intents import parse_intent
from execution.models import ExecutionStatus, SimulationOrderRequest
from risk.engine import RiskEngine
from risk.models import IntentAction, RiskDecision, RiskOutcome, RiskRequest, SignalConfidence


def test_non_simulation_mode_is_blocked_before_and_at_paper_broker(
    now,
    market_snapshot,
    safe_anti_rug,
    portfolio_state,
    simulation_broker,
    duckdb_store,
) -> None:
    live_decision = RiskEngine().evaluate(
        RiskRequest(
            action=IntentAction.BUY,
            confidence=SignalConfidence.HIGH,
            requested_notional_usd=Decimal("10"),
            portfolio=portfolio_state,
            market_data=market_snapshot.market_data_state(),
            anti_rug=safe_anti_rug,
            mode="live",
            now=now,
        )
    )
    broker_result = simulation_broker.submit(
        SimulationOrderRequest(
            risk_decision_id="risk-live-request",
            risk_decision=RiskDecision(
                outcome=RiskOutcome.APPROVED,
                action=IntentAction.BUY,
                reason_codes=("TEST_APPROVED_SIMULATION_ONLY",),
                approved_notional_usd=Decimal("10"),
            ),
            pair_id=market_snapshot.identity.pair_id,
            reference_price_usd=market_snapshot.metrics.price_usd,
            mode="live",
            created_at=now,
        )
    )
    stored_orders = duckdb_store.connection.execute(
        "SELECT COUNT(*) FROM simulated_orders"
    ).fetchone()[0]

    assert live_decision.outcome is RiskOutcome.HOLD
    assert live_decision.reason_codes == ("MODE_NOT_SIMULATION",)
    assert broker_result.status is ExecutionStatus.HOLD
    assert "EXECUTION_MODE_NOT_SIMULATION" in broker_result.reason_codes
    assert stored_orders == 0


def test_withdrawal_like_intent_is_not_a_bounded_action() -> None:
    parsed = parse_intent(
        json.dumps(
            {
                "intent": "WITHDRAW",
                "confidence": "high",
                "reason_codes": ["UNSUPPORTED"],
                "evidence_summary": ["forbidden action"],
                "risk_handoff_required": True,
                "requested_notional_usd": "1",
            }
        )
    )

    assert "WITHDRAW" not in {action.value for action in IntentAction}
    assert not parsed.ok
    assert parsed.reason_codes == ("LLM_OUTPUT_FIELDS_INVALID",)
