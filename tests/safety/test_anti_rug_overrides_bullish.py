from dataclasses import replace

from agents.orchestrator import AgentOrchestrator, OrchestrationContext
from agents.research_agent import ResearchAgent
from risk.models import RiskOutcome


class BrokerSpy:
    def __init__(self) -> None:
        self.requests = []

    def submit(self, request):
        self.requests.append(request)
        raise AssertionError("anti-rug hard fail must block paper execution")


def test_anti_rug_hard_fail_overrides_bullish_agent_intent(
    now,
    market_snapshot,
    technical_vector,
    safe_anti_rug,
    portfolio_state,
    buy_gateway,
) -> None:
    broker = BrokerSpy()
    result = AgentOrchestrator(
        agent=ResearchAgent(buy_gateway),
        broker=broker,
        risk_decision_id="risk-bullish-rug",
    ).run(
        OrchestrationContext(
            snapshot=market_snapshot,
            vector=technical_vector,
            anti_rug=replace(safe_anti_rug, honeypot_tax_route_or_sellability_issue=True),
            portfolio=portfolio_state,
            now=now,
        )
    )

    assert result.risk_decision is not None
    assert result.risk_decision.outcome is RiskOutcome.HOLD
    assert result.risk_decision.reason_codes == ("ANTI_RUG_HONEYPOT_OR_SELLABILITY",)
    assert result.executed is False
    assert broker.requests == []
