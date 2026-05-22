"""Bounded agent orchestration with risk-first simulation handoff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from agents.intents import BoundedIntent, BoundedIntentAction, hold_intent, parse_intent
from agents.research_agent import ResearchAgent
from data_pipeline.contracts import NormalizedMarketSnapshot
from data_pipeline.validation import validate_snapshot
from execution.models import ExecutionResult, SimulationOrderRequest
from execution.simulation_broker import SimulationBroker
from memory.research_memory import ResearchMemory
from risk.engine import RiskEngine
from risk.models import AntiRugEvidence, PortfolioState, RiskDecision, RiskOutcome, RiskRequest
from utils.results import ResultStatus
from utils.toon import JsonValue, UnsafePayloadError, serialize_toon


@dataclass(frozen=True)
class OrchestrationContext:
    snapshot: NormalizedMarketSnapshot | None
    vector: dict[str, JsonValue] | None
    anti_rug: AntiRugEvidence
    portfolio: PortfolioState
    now: datetime | None = None
    extra_payload: dict[str, JsonValue] | None = None


@dataclass(frozen=True)
class OrchestrationResult:
    intent: BoundedIntent
    risk_decision: RiskDecision | None
    execution_result: ExecutionResult | None
    reason_codes: tuple[str, ...]

    @property
    def executed(self) -> bool:
        return self.execution_result is not None and self.execution_result.executed


class AgentOrchestrator:
    def __init__(
        self,
        *,
        agent: ResearchAgent | None = None,
        risk_engine: RiskEngine | None = None,
        memory: ResearchMemory | None = None,
        broker: SimulationBroker | None = None,
        risk_decision_id: str | None = None,
    ) -> None:
        self.agent = agent or ResearchAgent()
        self.risk_engine = risk_engine or RiskEngine()
        self.memory = memory or ResearchMemory()
        self.broker = broker
        self.risk_decision_id = risk_decision_id

    def run(self, context: OrchestrationContext) -> OrchestrationResult:
        snapshot_result = validate_snapshot(context.snapshot, now=context.now)
        if not snapshot_result.ok or snapshot_result.value is None or context.vector is None:
            return _non_actionable(
                "MARKET_CONTEXT_INSUFFICIENT",
                action=BoundedIntentAction.INSUFFICIENT_DATA,
            )

        snapshot = snapshot_result.value
        payload: dict[str, JsonValue] = {
            "market": snapshot.toon_summary(),
            "vector": context.vector,
            "anti_rug": _anti_rug_payload(context.anti_rug),
            "portfolio": {
                "bankroll": str(context.portfolio.bankroll_usd),
                "exposure": str(context.portfolio.current_exposure_usd),
                "open_positions": context.portfolio.open_positions,
            },
        }
        if context.extra_payload:
            payload["extra"] = context.extra_payload
        try:
            raw_output = self.agent.propose(serialize_toon(payload))
        except UnsafePayloadError:
            return _non_actionable("PROMPT_PAYLOAD_UNSAFE", action=BoundedIntentAction.HOLD)

        parsed = parse_intent(raw_output)
        if not parsed.ok or parsed.value is None:
            fallback = (
                BoundedIntentAction.INSUFFICIENT_DATA
                if parsed.status is ResultStatus.INSUFFICIENT_DATA
                else BoundedIntentAction.HOLD
            )
            return _non_actionable(*parsed.reason_codes, action=fallback)

        intent = parsed.value
        self.memory.remember(pair_id=snapshot.identity.pair_id, intent=intent)
        if intent.action is BoundedIntentAction.INSUFFICIENT_DATA:
            return OrchestrationResult(intent, None, None, intent.reason_codes)

        risk_decision = self.risk_engine.evaluate(
            RiskRequest(
                action=intent.risk_action(),
                confidence=intent.confidence,
                requested_notional_usd=intent.requested_notional_usd,
                portfolio=context.portfolio,
                market_data=snapshot.market_data_state(),
                anti_rug=context.anti_rug,
                now=context.now,
            )
        )
        if risk_decision.outcome is not RiskOutcome.APPROVED:
            return OrchestrationResult(intent, risk_decision, None, risk_decision.reason_codes)
        if self.broker is None or not self.risk_decision_id:
            return OrchestrationResult(intent, risk_decision, None, ("RISK_APPROVED_HANDOFF",))

        execution = self.broker.submit(
            SimulationOrderRequest(
                risk_decision_id=self.risk_decision_id,
                risk_decision=risk_decision,
                pair_id=snapshot.identity.pair_id,
                reference_price_usd=snapshot.metrics.price_usd,
                created_at=context.now,
            )
        )
        return OrchestrationResult(intent, risk_decision, execution, execution.reason_codes)


def _non_actionable(*reason_codes: str, action: BoundedIntentAction) -> OrchestrationResult:
    intent = hold_intent(reason_codes[0])
    if action is BoundedIntentAction.INSUFFICIENT_DATA:
        intent = BoundedIntent(
            action=action,
            confidence=intent.confidence,
            reason_codes=tuple(reason_codes),
            evidence_summary=intent.evidence_summary,
        )
    return OrchestrationResult(intent, None, None, tuple(reason_codes))


def _anti_rug_payload(evidence: AntiRugEvidence) -> dict[str, bool | None]:
    return {
        "liquidity_accessible": evidence.liquidity_accessible,
        "liquidity_meets_floor": evidence.liquidity_meets_floor,
        "liquidity_status_known": evidence.liquidity_status_known,
        "sell_restriction": evidence.mint_freeze_or_sell_restriction,
        "holder_control": evidence.unsafe_holder_or_creator_control,
        "honeypot": evidence.honeypot_tax_route_or_sellability_issue,
        "identity_ambiguous": evidence.identity_ambiguous,
        "evidence_complete": evidence.evidence_complete,
    }
