from datetime import datetime, timedelta, timezone
from decimal import Decimal

from execution.audit import ExecutionAudit
from execution.execution_daemon import ExecutionDaemon
from execution.models import ExecutionStatus, SimulationOrderRequest
from execution.simulation_broker import SimulationBroker
from risk.engine import RiskEngine
from risk.models import (
    AntiRugEvidence,
    IntentAction,
    MarketDataState,
    PortfolioState,
    RiskRequest,
    SignalConfidence,
)
from storage.duckdb_store import DuckDBStore
from storage.repositories import AuditRepository, ResearchRepository, SimulationRepository
from storage.schema import initialize_schema

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_risk_approved_execution_flow_persists_paper_records() -> None:
    request = RiskRequest(
        action=IntentAction.BUY,
        confidence=SignalConfidence.HIGH,
        requested_notional_usd=Decimal("10"),
        portfolio=PortfolioState(
            bankroll_usd=Decimal("50"),
            current_exposure_usd=Decimal("0"),
            open_positions=0,
            daily_loss_usd=Decimal("0"),
        ),
        market_data=MarketDataState(
            observed_at=NOW - timedelta(minutes=1),
            provenance_known=True,
        ),
        anti_rug=AntiRugEvidence(
            liquidity_accessible=True,
            liquidity_meets_floor=True,
            liquidity_status_known=True,
            mint_freeze_or_sell_restriction=False,
            unsafe_holder_or_creator_control=False,
            honeypot_tax_route_or_sellability_issue=False,
            identity_ambiguous=False,
            evidence_complete=True,
        ),
        now=NOW,
    )
    risk_decision = RiskEngine().evaluate(request)

    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        research = ResearchRepository(store.connection)
        decision_id = research.record_risk_decision(
            decision=risk_decision.outcome.value,
            reason_codes=risk_decision.reason_codes,
            details={"mode": "simulation", "approval": risk_decision.approved},
            decided_at=NOW,
        )
        daemon = ExecutionDaemon(
            SimulationBroker(
                repository=SimulationRepository(store.connection),
                audit=ExecutionAudit(AuditRepository(store.connection)),
            )
        )

        result = daemon.process(
            SimulationOrderRequest(
                risk_decision_id=decision_id,
                risk_decision=risk_decision,
                pair_id="fixture-sol-usdc",
                reference_price_usd=Decimal("4"),
                created_at=NOW,
            )
        )
        counts = store.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM risk_decisions),
                (SELECT COUNT(*) FROM simulated_orders),
                (SELECT COUNT(*) FROM simulated_fills),
                (SELECT COUNT(*) FROM audit_events)
            """
        ).fetchone()

    assert result.status is ExecutionStatus.FILLED
    assert result.fill is not None
    assert result.fill.quantity == Decimal("2.487562189054")
    assert counts == (1, 1, 1, 2)

