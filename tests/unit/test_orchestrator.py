import json
from datetime import datetime, timezone
from decimal import Decimal

from agents.llm_gateway import MockResearchGateway
from agents.orchestrator import AgentOrchestrator, OrchestrationContext
from agents.research_agent import ResearchAgent
from data_pipeline.normalization import normalize_market_record
from risk.models import AntiRugEvidence, PortfolioState, RiskOutcome

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


class BrokerSpy:
    def __init__(self) -> None:
        self.requests = []

    def submit(self, request):
        self.requests.append(request)
        raise AssertionError("blocked risk decisions must not execute")


def test_buy_blocked_by_anti_rug_never_reaches_broker() -> None:
    spy = BrokerSpy()
    orchestrator = AgentOrchestrator(
        agent=ResearchAgent(
            MockResearchGateway(
                lambda *_args: json.dumps(
                    {
                        "intent": "BUY",
                        "confidence": "high",
                        "reason_codes": ["MOMENTUM"],
                        "evidence_summary": ["fixture signal"],
                        "risk_handoff_required": True,
                        "requested_notional_usd": "10",
                    }
                )
            )
        ),
        broker=spy,
        risk_decision_id="risk-test",
    )

    result = orchestrator.run(context(identity_ambiguous=True))

    assert result.risk_decision is not None
    assert result.risk_decision.outcome is RiskOutcome.HOLD
    assert result.executed is False
    assert spy.requests == []


def test_missing_market_data_is_insufficient_before_gateway() -> None:
    gateway = MockResearchGateway()
    orchestrator = AgentOrchestrator(agent=ResearchAgent(gateway))

    result = orchestrator.run(
        OrchestrationContext(
            snapshot=None,
            vector={"pair": "fixture"},
            anti_rug=safe_anti_rug(),
            portfolio=portfolio(),
            now=NOW,
        )
    )

    assert result.intent.action.value == "INSUFFICIENT_DATA"
    assert result.reason_codes == ("MARKET_CONTEXT_INSUFFICIENT",)
    assert gateway.calls == []


def context(*, identity_ambiguous: bool = False) -> OrchestrationContext:
    snapshot = normalize_market_record(
        {
            "pair_id": "sol-usdc",
            "chain_id": "solana",
            "base_symbol": "SOL",
            "quote_symbol": "USDC",
            "price_usd": "4.2",
            "liquidity_usd": "12000",
            "volume_24h_usd": "3000",
            "observed_at": "2026-05-22T11:59:00+00:00",
            "source_record_id": "fixture",
        },
        source_name="fixture",
        now=NOW,
    ).value
    assert snapshot is not None
    return OrchestrationContext(
        snapshot=snapshot,
        vector={"pair": "sol-usdc", "px": 4.2},
        anti_rug=safe_anti_rug(identity_ambiguous=identity_ambiguous),
        portfolio=portfolio(),
        now=NOW,
    )


def safe_anti_rug(*, identity_ambiguous: bool = False) -> AntiRugEvidence:
    return AntiRugEvidence(
        liquidity_accessible=True,
        liquidity_meets_floor=True,
        liquidity_status_known=True,
        mint_freeze_or_sell_restriction=False,
        unsafe_holder_or_creator_control=False,
        honeypot_tax_route_or_sellability_issue=False,
        identity_ambiguous=identity_ambiguous,
        evidence_complete=True,
    )


def portfolio() -> PortfolioState:
    return PortfolioState(
        bankroll_usd=Decimal("50"),
        current_exposure_usd=Decimal("0"),
        open_positions=0,
        daily_loss_usd=Decimal("0"),
    )

