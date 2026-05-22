from datetime import datetime, timezone
from decimal import Decimal

from execution.audit import ExecutionAudit
from execution.models import ExecutionStatus, SimulationOrderRequest
from execution.simulation_broker import SimulationBroker
from risk.models import IntentAction, RiskDecision, RiskOutcome
from storage.duckdb_store import DuckDBStore
from storage.repositories import AuditRepository, SimulationRepository
from storage.schema import initialize_schema

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def approved_request(
    *,
    fill_fraction: Decimal = Decimal("1"),
    approved_notional_usd: Decimal = Decimal("10"),
) -> SimulationOrderRequest:
    return SimulationOrderRequest(
        risk_decision_id="risk_approved",
        risk_decision=RiskDecision(
            outcome=RiskOutcome.APPROVED,
            action=IntentAction.BUY,
            reason_codes=("RISK_APPROVED_SIMULATION_ONLY",),
            approved_notional_usd=approved_notional_usd,
        ),
        pair_id="fixture-sol-usdc",
        reference_price_usd=Decimal("4"),
        fill_fraction=fill_fraction,
        created_at=NOW,
    )


def test_simulation_broker_persists_partial_fill_and_audit_events() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        broker = SimulationBroker(
            repository=SimulationRepository(store.connection),
            audit=ExecutionAudit(AuditRepository(store.connection)),
        )

        result = broker.submit(approved_request(fill_fraction=Decimal("0.5")))
        persisted = store.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM simulated_orders),
                (SELECT COUNT(*) FROM simulated_fills),
                (SELECT COUNT(*) FROM audit_events)
            """
        ).fetchone()

    assert result.status is ExecutionStatus.PARTIALLY_FILLED
    assert result.fill is not None
    assert result.fill.notional_usd == Decimal("5.00000000")
    assert result.fill.price_usd == Decimal("4.020000000000")
    assert persisted == (1, 1, 2)


def test_broker_rechecks_config_max_position_size() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        broker = SimulationBroker(
            repository=SimulationRepository(store.connection),
            audit=ExecutionAudit(AuditRepository(store.connection)),
        )

        result = broker.submit(approved_request(approved_notional_usd=Decimal("10.01")))
        persisted = store.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM simulated_orders),
                (SELECT COUNT(*) FROM simulated_fills),
                (SELECT COUNT(*) FROM audit_events)
            """
        ).fetchone()

    assert result.status is ExecutionStatus.HOLD
    assert result.reason_codes == ("CONFIG_MAX_POSITION_EXCEEDED",)
    assert persisted == (0, 0, 2)


def test_hold_and_insufficient_risk_decisions_do_not_execute() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        broker = SimulationBroker(
            repository=SimulationRepository(store.connection),
            audit=ExecutionAudit(AuditRepository(store.connection)),
        )
        hold = broker.submit(
            SimulationOrderRequest(
                risk_decision_id="risk_hold",
                risk_decision=RiskDecision(
                    outcome=RiskOutcome.HOLD,
                    action=IntentAction.HOLD,
                    reason_codes=("INTENT_DEFAULT_HOLD",),
                ),
                pair_id="fixture-sol-usdc",
                reference_price_usd=Decimal("4"),
                created_at=NOW,
            )
        )
        insufficient = broker.submit(
            SimulationOrderRequest(
                risk_decision_id="risk_insufficient",
                risk_decision=RiskDecision(
                    outcome=RiskOutcome.INSUFFICIENT_DATA,
                    action=IntentAction.BUY,
                    reason_codes=("TIMESTAMP_STALE",),
                ),
                pair_id="fixture-sol-usdc",
                reference_price_usd=Decimal("4"),
                created_at=NOW,
            )
        )
        persisted = store.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM simulated_orders),
                (SELECT COUNT(*) FROM simulated_fills),
                (SELECT COUNT(*) FROM audit_events)
            """
        ).fetchone()

    assert hold.status is ExecutionStatus.HOLD
    assert hold.executed is False
    assert insufficient.status is ExecutionStatus.INSUFFICIENT_DATA
    assert insufficient.executed is False
    assert persisted == (0, 0, 4)
