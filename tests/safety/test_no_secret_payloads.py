from datetime import datetime, timezone
from decimal import Decimal

from agents.llm_gateway import MockResearchGateway
from agents.orchestrator import AgentOrchestrator, OrchestrationContext
from agents.research_agent import ResearchAgent
from data_pipeline.normalization import normalize_market_record
from risk.models import AntiRugEvidence, PortfolioState

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_secret_like_payload_is_blocked_before_gateway_call() -> None:
    gateway = MockResearchGateway()
    snapshot = normalize_market_record(
        {
            "pair_id": "pair",
            "chain_id": "solana",
            "base_symbol": "SOL",
            "quote_symbol": "USDC",
            "price_usd": "4.2",
            "liquidity_usd": "10000",
            "volume_24h_usd": "2000",
            "observed_at": "2026-05-22T11:59:00+00:00",
            "source_record_id": "fixture",
        },
        source_name="fixture",
        now=NOW,
    ).value
    assert snapshot is not None

    result = AgentOrchestrator(agent=ResearchAgent(gateway)).run(
        OrchestrationContext(
            snapshot=snapshot,
            vector={"pair": "pair", "px": 4.2},
            anti_rug=AntiRugEvidence(True, True, True, False, False, False, False, True),
            portfolio=PortfolioState(Decimal("50"), Decimal("0"), 0, Decimal("0")),
            now=NOW,
            extra_payload={"private_key": "blocked"},
        )
    )

    assert result.reason_codes == ("PROMPT_PAYLOAD_UNSAFE",)
    assert gateway.calls == []

