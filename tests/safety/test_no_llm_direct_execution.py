import json

from agents.llm_gateway import MockResearchGateway
from agents.orchestrator import AgentOrchestrator, OrchestrationContext
from agents.research_agent import ResearchAgent


class BrokerSpy:
    def __init__(self) -> None:
        self.requests = []

    def submit(self, request):
        self.requests.append(request)
        raise AssertionError("raw LLM output cannot reach execution")


def test_raw_llm_execution_fields_are_non_actionable(
    now,
    market_snapshot,
    technical_vector,
    safe_anti_rug,
    portfolio_state,
) -> None:
    broker = BrokerSpy()
    result = AgentOrchestrator(
        agent=ResearchAgent(
            MockResearchGateway(
                lambda *_args: json.dumps(
                    {
                        "intent": "BUY",
                        "confidence": "high",
                        "reason_codes": ["RAW_EXECUTION_REQUEST"],
                        "evidence_summary": ["should be rejected"],
                        "risk_handoff_required": True,
                        "requested_notional_usd": "10",
                        "execute_now": True,
                    }
                )
            )
        ),
        broker=broker,
        risk_decision_id="risk-raw-llm",
    ).run(
        OrchestrationContext(
            snapshot=market_snapshot,
            vector=technical_vector,
            anti_rug=safe_anti_rug,
            portfolio=portfolio_state,
            now=now,
        )
    )

    assert result.reason_codes == ("LLM_OUTPUT_EXTRA_FIELDS",)
    assert result.executed is False
    assert broker.requests == []
