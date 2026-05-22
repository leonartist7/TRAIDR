from datetime import datetime, timezone
from decimal import Decimal

from agents.orchestrator import AgentOrchestrator, OrchestrationContext
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

