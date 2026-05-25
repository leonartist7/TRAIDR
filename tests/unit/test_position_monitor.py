from datetime import datetime, timedelta, timezone
from decimal import Decimal

from portfolio.position_monitor import monitor_positions
from portfolio.repository import PortfolioRepository
from portfolio.service import PortfolioService
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository, ResearchRepository
from storage.schema import initialize_schema

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=1)


def test_position_monitor_reads_local_evidence_and_flags_exit_candidate() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        service = PortfolioService(PortfolioRepository(store.connection))
        service.add(
            symbol="BONK",
            chain="solana",
            pair_ref="solana/BONK",
            entry_price=Decimal("1"),
            size_usd=Decimal("20"),
            thesis="meme momentum",
            stop_zone="below 0.90",
            now=NOW,
        )
        research = ResearchRepository(store.connection)
        research.record_evidence(
            source_name="market_scan:fixture",
            observed_at=NOW,
            quality_status="sufficient",
            payload={
                "pair_id": "BONK",
                "source": "fixture",
                "observed_at": NOW.isoformat(),
                "price_usd": "1.20",
                "liquidity_usd": "10000",
                "volume_24h_usd": "1000",
                "data_quality": "sufficient",
                "can_execute_trades": False,
            },
            provenance={"source": "fixture", "pair_id": "BONK", "can_execute_trades": False},
            collected_at=NOW,
        )
        research.record_evidence(
            source_name="market_scan:fixture",
            observed_at=LATER,
            quality_status="sufficient",
            payload={
                "pair_id": "BONK",
                "source": "fixture",
                "observed_at": LATER.isoformat(),
                "price_usd": "0.80",
                "liquidity_usd": "4000",
                "volume_24h_usd": "1000",
                "data_quality": "sufficient",
                "can_execute_trades": False,
            },
            provenance={"source": "fixture", "pair_id": "BONK", "can_execute_trades": False},
            collected_at=LATER,
        )
        intelligence = IntelligenceRepository(store.connection)
        intelligence.record_radar_state(
            subject_id="BONK",
            state="WATCH",
            rank=1,
            opportunity_score=80,
            risk_score=30,
            confidence=0.8,
            reason_codes=("PREVIOUS",),
            payload={"can_execute_trades": False},
            recorded_at=NOW,
        )
        intelligence.record_radar_state(
            subject_id="BONK",
            state="AVOID",
            rank=1,
            opportunity_score=20,
            risk_score=90,
            confidence=0.8,
            reason_codes=("TOKEN_SAFETY_UNKNOWN",),
            payload={"can_execute_trades": False},
            recorded_at=LATER,
        )

        decisions = monitor_positions(store.connection, now=NOW)

    assert decisions[0].state.value == "EXIT_CANDIDATE"
    assert "RADAR_STATE_AVOID" in decisions[0].reason_codes
    assert decisions[0].can_execute_trades is False


def test_position_monitor_returns_empty_without_positions() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        decisions = monitor_positions(store.connection, now=NOW)

    assert decisions == ()
