from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from agents.llm_gateway import MockResearchGateway
from agents.orchestrator import AgentOrchestrator, OrchestrationContext
from agents.research_agent import ResearchAgent
from risk.models import AntiRugEvidence, PortfolioState

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_orchestrator_missing_market_data_never_executes() -> None:
    result = AgentOrchestrator().run(
        OrchestrationContext(
            snapshot=None,
            vector=None,
            anti_rug=AntiRugEvidence(None, None, None, None, None, None, None, None),
            portfolio=PortfolioState(Decimal("50"), Decimal("0"), 0, Decimal("0")),
            now=NOW,
        )
    )

    assert result.executed is False
    assert result.intent.action.value == "INSUFFICIENT_DATA"


def test_stale_market_snapshot_is_insufficient_before_execution(
    now,
    market_snapshot,
    technical_vector,
    safe_anti_rug,
    portfolio_state,
    simulation_broker,
    duckdb_store,
) -> None:
    gateway = MockResearchGateway()
    stale_snapshot = replace(
        market_snapshot,
        freshness=replace(
            market_snapshot.freshness,
            observed_at=now - timedelta(minutes=10),
        ),
    )
    result = AgentOrchestrator(
        agent=ResearchAgent(gateway),
        broker=simulation_broker,
        risk_decision_id="risk-stale-market",
    ).run(
        OrchestrationContext(
            snapshot=stale_snapshot,
            vector=technical_vector,
            anti_rug=safe_anti_rug,
            portfolio=portfolio_state,
            now=now,
        )
    )
    stored_orders = duckdb_store.connection.execute(
        "SELECT COUNT(*) FROM simulated_orders"
    ).fetchone()[0]

    assert result.executed is False
    assert result.intent.action.value == "INSUFFICIENT_DATA"
    assert result.reason_codes == ("MARKET_CONTEXT_INSUFFICIENT",)
    assert gateway.calls == []
    assert stored_orders == 0
