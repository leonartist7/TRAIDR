from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from dashboard.queries import load_dashboard_data
from portfolio.repository import PortfolioRepository
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository, ResearchRepository
from storage.schema import initialize_schema


def test_dashboard_queries_missing_database_is_read_only(tmp_path: Path) -> None:
    database = tmp_path / "missing-dashboard.duckdb"

    data = load_dashboard_data(database)

    assert data.database_exists is False
    assert database.exists() is False
    assert data.safety_status["live_trading_implemented"] is False


def test_dashboard_queries_load_command_center_sections(tmp_path: Path) -> None:
    database = tmp_path / "dashboard.duckdb"
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        research = ResearchRepository(store.connection)
        intelligence = IntelligenceRepository(store.connection)
        research.record_evidence(
            source_name="market_scan:fixture",
            observed_at=now,
            quality_status="sufficient",
            payload={
                "pair_id": "fixture-sol-usdc",
                "source": "fixture",
                "can_execute_trades": False,
            },
            provenance={"source": "fixture", "can_execute_trades": False},
            collected_at=now,
        )
        intelligence.record_radar_state(
            subject_id="fixture-sol-usdc",
            state="WATCH",
            rank=1,
            opportunity_score=45.0,
            risk_score=35.0,
            confidence=0.6,
            reason_codes=("TEST_RADAR",),
            payload={"can_execute_trades": False},
            recorded_at=now,
        )
        intelligence.record_notification_alert(
            subject_id="fixture-sol-usdc",
            channel="local",
            severity="WARNING",
            fingerprint="fixture",
            status="RECORDED_ONLY",
            reason_codes=("TEST_ALERT",),
            payload={"can_execute_trades": False},
            recorded_at=now,
        )
        PortfolioRepository(store.connection).add_entry(
            symbol="SOL",
            chain="solana",
            pair_ref="solana/SOL",
            entry_price=Decimal("4.20"),
            size_usd=Decimal("20"),
            thesis="manual research",
            created_at=now,
        )

    data = load_dashboard_data(database)

    assert data.database_exists is True
    assert data.market_radar[0]["can_execute_trades"] is False
    assert data.scan_evidence[0]["source_name"] == "market_scan:fixture"
    assert data.alerts[0]["subject_id"] == "fixture-sol-usdc"
    assert data.portfolio_entries[0]["symbol"] == "SOL"
