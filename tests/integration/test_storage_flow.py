from datetime import datetime, timezone
from decimal import Decimal

from storage.duckdb_store import DuckDBStore
from storage.repositories import AuditRepository, ResearchRepository, SimulationRepository
from storage.schema import initialize_schema


def test_repositories_write_safe_duckdb_records() -> None:
    timestamp = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        research = ResearchRepository(store.connection)
        audit = AuditRepository(store.connection)
        simulation = SimulationRepository(store.connection)

        snapshot_id = research.record_evidence(
            source_name="fixture_snapshots",
            observed_at=timestamp,
            collected_at=timestamp,
            quality_status="validated",
            payload={"pair": "SOL/USDC", "liquidity_usd": 12000.0},
            provenance={"source": "fixture", "mode": "simulation"},
        )
        vector_id = research.record_vector(
            snapshot_id=snapshot_id,
            feature_status="sufficient",
            features={"pair": "SOL/USDC", "freshness": "fresh"},
            created_at=timestamp,
        )
        intent_id = research.record_intent(
            intent="HOLD",
            output_status="INSUFFICIENT_DATA",
            reason_codes=["ANTI_RUG_EVIDENCE_REQUIRED"],
            payload={"intent": "HOLD", "evidence": ["simulation only"]},
            created_at=timestamp,
        )
        decision_id = research.record_risk_decision(
            intent_id=intent_id,
            decision="HOLD",
            reason_codes=["ANTI_RUG_EVIDENCE_REQUIRED"],
            details={"authority": "deterministic", "mode": "simulation"},
            decided_at=timestamp,
        )
        order_id = simulation.record_order(
            risk_decision_id=decision_id,
            side="BUY",
            pair_id="fixture-sol-usdc",
            notional_usd=Decimal("5.00000000"),
            order_status="paper_pending",
            metadata={"mode": "simulation"},
            created_at=timestamp,
        )
        fill_id = simulation.record_fill(
            order_id=order_id,
            quantity=Decimal("1.250000000000"),
            price_usd=Decimal("4.000000000000"),
            notional_usd=Decimal("5.00000000"),
            metadata={"fill_type": "paper"},
            filled_at=timestamp,
        )
        event_id = audit.append_event(
            event_type="storage_flow",
            severity="INFO",
            reason_codes=["SIMULATION_RECORDS_WRITTEN"],
            payload={"snapshot_id": snapshot_id, "vector_id": vector_id},
            recorded_at=timestamp,
        )

        counts = {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "evidence_snapshots",
                "technical_vectors",
                "research_intents",
                "risk_decisions",
                "simulated_orders",
                "simulated_fills",
                "audit_events",
            )
        }
        persisted = store.connection.execute(
            """
            SELECT
                (SELECT output_status FROM research_intents WHERE intent_id = ?),
                (SELECT payload_toon FROM research_intents WHERE intent_id = ?),
                (SELECT event_type FROM audit_events WHERE event_id = ?),
                (SELECT order_id FROM simulated_fills WHERE fill_id = ?)
            """,
            [intent_id, intent_id, event_id, fill_id],
        ).fetchone()

    assert counts == {
        "evidence_snapshots": 1,
        "technical_vectors": 1,
        "research_intents": 1,
        "risk_decisions": 1,
        "simulated_orders": 1,
        "simulated_fills": 1,
        "audit_events": 1,
    }
    assert persisted == (
        "INSUFFICIENT_DATA",
        "intent: HOLD\nevidence[1]: simulation only",
        "storage_flow",
        order_id,
    )

