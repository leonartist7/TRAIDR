from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from data_pipeline.bitunix_models import BitunixCandle, BitunixTradingPair
from dashboard.queries import load_dashboard_data, load_market_candles, load_market_instruments
from portfolio.repository import PortfolioRepository
from storage.duckdb_store import DuckDBStore
from storage.market_repository import MarketRepository
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
    assert data.market_radar == []
    assert data.scan_evidence[0]["source_name"] == "market_scan:fixture"
    assert data.alerts[0]["subject_id"] == "fixture-sol-usdc"
    assert data.portfolio_entries[0]["symbol"] == "SOL"


def test_dashboard_queries_load_recent_candles_read_only(tmp_path: Path) -> None:
    database = tmp_path / "market-candles.duckdb"
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)
    candles = [
        BitunixCandle(
            symbol="BTCUSDT",
            interval="1h",
            time_ms=1_700_000_000_000 + (index * 3_600_000),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal(str(100 + index)),
            quote_volume=Decimal("1000"),
            base_volume=Decimal("10"),
        )
        for index in range(3)
    ]
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        assert MarketRepository(store.connection).upsert_candles(
            "bitunix:BTCUSDT",
            "1h",
            candles,
            received_at=now,
        ) == 3

    rows = load_market_candles(database, "bitunix:BTCUSDT", "1h", limit=2)

    assert [row["open_time_ms"] for row in rows] == [candles[1].time_ms, candles[2].time_ms]
    assert all(row["can_execute_trades"] is False for row in rows)
    with pytest.raises(ValueError, match="unsupported market interval"):
        load_market_candles(database, "bitunix:BTCUSDT", "2h")


def test_dashboard_queries_load_market_instruments_read_only(tmp_path: Path) -> None:
    database = tmp_path / "market-instruments.duckdb"
    now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)
    pair = BitunixTradingPair(
        symbol="BTCUSDT",
        base="BTC",
        quote="USDT",
        min_trade_volume=1,
        min_buy_price_offset=0,
        max_sell_price_offset=0,
        max_limit_order_volume=100,
        max_market_order_volume=100,
        base_precision=3,
        quote_precision=2,
        min_leverage=1,
        max_leverage=10,
        default_leverage=1,
        default_margin_mode="isolated",
        price_protect_scope=1,
        symbol_status="TRADING",
        is_api_supported=True,
        max_funding_rate=1,
        min_funding_rate=-1,
    )
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        MarketRepository(store.connection).upsert_instrument(pair, now=now)

    rows = load_market_instruments(database)

    assert rows[0]["instrument_id"] == "bitunix:BTCUSDT"
    assert rows[0]["status"] == "TRADING"
    assert rows[0]["can_execute_trades"] is False
