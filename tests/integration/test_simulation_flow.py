from agents.orchestrator import AgentOrchestrator, OrchestrationContext
from agents.research_agent import ResearchAgent
from execution.models import ExecutionStatus
from risk.models import RiskOutcome


def test_fixture_market_to_duckdb_paper_audit_flow(
    now,
    market_snapshot,
    technical_vector,
    safe_anti_rug,
    portfolio_state,
    buy_gateway,
    simulation_broker,
    duckdb_store,
) -> None:
    result = AgentOrchestrator(
        agent=ResearchAgent(buy_gateway),
        broker=simulation_broker,
        risk_decision_id="risk-approved-fixture-flow",
    ).run(
        OrchestrationContext(
            snapshot=market_snapshot,
            vector=technical_vector,
            anti_rug=safe_anti_rug,
            portfolio=portfolio_state,
            now=now,
        )
    )

    counts = duckdb_store.connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM simulated_orders),
            (SELECT COUNT(*) FROM simulated_fills),
            (SELECT COUNT(*) FROM audit_events)
        """
    ).fetchone()
    audit_types = duckdb_store.connection.execute(
        "SELECT event_type FROM audit_events ORDER BY recorded_at, event_id"
    ).fetchall()

    assert result.risk_decision is not None
    assert result.risk_decision.outcome is RiskOutcome.APPROVED
    assert result.execution_result is not None
    assert result.execution_result.status is ExecutionStatus.FILLED
    assert result.executed is True
    assert counts == (1, 1, 2)
    assert set(audit_types) == {
        ("simulation_execution_attempt",),
        ("simulation_execution_fill",),
    }


def test_hold_intent_never_writes_paper_execution(
    now,
    market_snapshot,
    technical_vector,
    safe_anti_rug,
    portfolio_state,
    simulation_broker,
    duckdb_store,
) -> None:
    result = AgentOrchestrator(
        broker=simulation_broker,
        risk_decision_id="risk-default-hold",
    ).run(
        OrchestrationContext(
            snapshot=market_snapshot,
            vector=technical_vector,
            anti_rug=safe_anti_rug,
            portfolio=portfolio_state,
            now=now,
        )
    )

    counts = duckdb_store.connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM simulated_orders),
            (SELECT COUNT(*) FROM simulated_fills),
            (SELECT COUNT(*) FROM audit_events)
        """
    ).fetchone()

    assert result.risk_decision is not None
    assert result.risk_decision.outcome is RiskOutcome.HOLD
    assert result.executed is False
    assert counts == (0, 0, 0)
