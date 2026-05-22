import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from agents.llm_gateway import MockResearchGateway
from data_pipeline.normalization import normalize_market_record
from execution.audit import ExecutionAudit
from execution.simulation_broker import SimulationBroker
from risk.models import AntiRugEvidence, PortfolioState
from storage.duckdb_store import DuckDBStore
from storage.repositories import AuditRepository, SimulationRepository
from storage.schema import initialize_schema
from technicals.vector_engine import build_technical_vector


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def market_snapshot(now: datetime):
    result = normalize_market_record(
        {
            "pair_id": "fixture-sol-usdc",
            "chain_id": "solana",
            "base_symbol": "SOL",
            "quote_symbol": "USDC",
            "price_usd": "4.20",
            "liquidity_usd": "12000",
            "volume_24h_usd": "3000",
            "observed_at": "2026-05-22T11:59:00+00:00",
            "source_record_id": "fixture-market",
        },
        source_name="fixture",
        retrieved_at=now,
        now=now,
    )
    assert result.ok
    assert result.value is not None
    return result.value


@pytest.fixture
def ohlcv_candles() -> list[dict[str, str]]:
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


@pytest.fixture
def technical_vector(market_snapshot, ohlcv_candles):
    result = build_technical_vector(
        pair_id=market_snapshot.identity.pair_id,
        candles=ohlcv_candles,
    )
    assert result.ok
    assert result.value is not None
    return result.value


@pytest.fixture
def safe_anti_rug() -> AntiRugEvidence:
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


@pytest.fixture
def portfolio_state() -> PortfolioState:
    return PortfolioState(
        bankroll_usd=Decimal("50"),
        current_exposure_usd=Decimal("0"),
        open_positions=0,
        daily_loss_usd=Decimal("0"),
    )


@pytest.fixture
def duckdb_store():
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        yield store


@pytest.fixture
def simulation_broker(duckdb_store) -> SimulationBroker:
    return SimulationBroker(
        repository=SimulationRepository(duckdb_store.connection),
        audit=ExecutionAudit(AuditRepository(duckdb_store.connection)),
    )


@pytest.fixture
def buy_gateway() -> MockResearchGateway:
    return MockResearchGateway(
        lambda *_args: json.dumps(
            {
                "intent": "BUY",
                "confidence": "high",
                "reason_codes": ["FIXTURE_SIGNAL"],
                "evidence_summary": ["deterministic fixture vector"],
                "risk_handoff_required": True,
                "requested_notional_usd": "10",
            }
        )
    )
