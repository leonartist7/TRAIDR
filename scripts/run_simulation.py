"""Run one deterministic local TRAIDR paper simulation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm_gateway import MockResearchGateway
from agents.orchestrator import AgentOrchestrator, OrchestrationContext
from agents.research_agent import ResearchAgent
from data_pipeline.normalization import normalize_market_record
from execution.audit import ExecutionAudit
from execution.simulation_broker import SimulationBroker
from risk.models import AntiRugEvidence, PortfolioState
from storage.duckdb_store import DuckDBStore
from storage.repositories import AuditRepository, SimulationRepository
from storage.schema import initialize_schema
from technicals.vector_engine import build_technical_vector

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one offline TRAIDR paper simulation.")
    parser.add_argument(
        "--database",
        default=":memory:",
        help="DuckDB target for paper records; defaults to an in-memory database.",
    )
    args = parser.parse_args()

    snapshot = _fixture_snapshot()
    vector_result = build_technical_vector(
        pair_id=snapshot.identity.pair_id,
        candles=_fixture_candles(),
    )
    if not vector_result.ok or vector_result.value is None:
        print("Simulation stopped: deterministic fixture vector is insufficient.")
        return 1

    with DuckDBStore(args.database) as store:
        initialize_schema(store.connection)
        broker = SimulationBroker(
            repository=SimulationRepository(store.connection),
            audit=ExecutionAudit(AuditRepository(store.connection)),
        )
        result = AgentOrchestrator(
            agent=ResearchAgent(_fixture_buy_gateway()),
            broker=broker,
            risk_decision_id="risk-script-fixture",
        ).run(
            OrchestrationContext(
                snapshot=snapshot,
                vector=vector_result.value,
                anti_rug=_safe_anti_rug(),
                portfolio=PortfolioState(
                    bankroll_usd=Decimal("50"),
                    current_exposure_usd=Decimal("0"),
                    open_positions=0,
                    daily_loss_usd=Decimal("0"),
                ),
                now=NOW,
            )
        )
        counts = store.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM simulated_orders),
                (SELECT COUNT(*) FROM simulated_fills),
                (SELECT COUNT(*) FROM audit_events)
            """
        ).fetchone()

    execution = result.execution_result
    risk_status = result.risk_decision.outcome.value if result.risk_decision else "NOT_RUN"
    risk_reasons = result.risk_decision.reason_codes if result.risk_decision else result.reason_codes
    execution_status = execution.status.value if execution else "NOT_EXECUTED"
    execution_reasons = execution.reason_codes if execution else result.reason_codes
    fill_id = execution.fill.fill_id if execution and execution.fill else "none"

    print("TRAIDR local simulation summary")
    print("Mode: simulation only")
    print(f"Database: {args.database}")
    print(f"Pair: {snapshot.identity.pair_id}")
    print(f"Vector status: {vector_result.status.value}")
    print(f"Intent: {result.intent.action.value}")
    print(f"Risk: {risk_status} ({', '.join(risk_reasons)})")
    print(f"Execution: {execution_status} ({', '.join(execution_reasons)})")
    print(f"Paper fill id: {fill_id}")
    print(f"Stored records: orders={counts[0]} fills={counts[1]} audit_events={counts[2]}")
    return 0


def _fixture_snapshot():
    normalized = normalize_market_record(
        {
            "pair_id": "fixture-sol-usdc",
            "chain_id": "solana",
            "base_symbol": "SOL",
            "quote_symbol": "USDC",
            "price_usd": "4.20",
            "liquidity_usd": "12000",
            "volume_24h_usd": "3000",
            "observed_at": "2026-05-22T11:59:00+00:00",
            "source_record_id": "script-fixture",
        },
        source_name="fixture",
        retrieved_at=NOW,
        now=NOW,
    )
    if not normalized.ok or normalized.value is None:
        raise RuntimeError("deterministic market fixture failed normalization")
    return normalized.value


def _fixture_candles() -> list[dict[str, str]]:
    return [
        {
            "timestamp": "2026-05-22T11:56:00+00:00",
            "open": "4.00",
            "high": "4.10",
            "low": "3.95",
            "close": "4.05",
            "volume": "1000",
        },
        {
            "timestamp": "2026-05-22T11:57:00+00:00",
            "open": "4.05",
            "high": "4.18",
            "low": "4.00",
            "close": "4.12",
            "volume": "850",
        },
        {
            "timestamp": "2026-05-22T11:58:00+00:00",
            "open": "4.12",
            "high": "4.24",
            "low": "4.08",
            "close": "4.20",
            "volume": "900",
        },
    ]


def _fixture_buy_gateway() -> MockResearchGateway:
    return MockResearchGateway(
        lambda *_args: json.dumps(
            {
                "intent": "BUY",
                "confidence": "high",
                "reason_codes": ["SCRIPT_FIXTURE_SIGNAL"],
                "evidence_summary": ["offline deterministic fixture"],
                "risk_handoff_required": True,
                "requested_notional_usd": "10",
            }
        )
    )


def _safe_anti_rug() -> AntiRugEvidence:
    return AntiRugEvidence(
        liquidity_accessible=True,
        liquidity_meets_floor=True,
        liquidity_status_known=True,
        mint_freeze_or_sell_restriction=False,
        unsafe_holder_or_creator_control=False,
        honeypot_tax_route_or_sellability_issue=False,
        identity_ambiguous=False,
        evidence_complete=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
