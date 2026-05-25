from datetime import datetime, timezone

from data_pipeline.live_market_loader import LiveMarketLoader
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository, ResearchRepository
from storage.schema import initialize_schema
from watchlist.models import WatchScanRecord
from watchlist.repository import WatchlistRepository
from watchlist.service import WatchlistService

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_watchlist_add_list_remove() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        service = WatchlistService(WatchlistRepository(store.connection))

        entry = service.add("solana/PAIR123", note="watch liquidity", tags=("solana",), now=NOW)
        listed = service.list()
        removed = service.remove("solana/PAIR123")

    assert entry.pair_ref == "solana/PAIR123"
    assert entry.can_execute_trades is False
    assert listed[0].tags == ("solana",)
    assert removed is True


def test_watch_scan_is_read_only_and_records_scores() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        service = WatchlistService(
            WatchlistRepository(store.connection),
            research_repository=ResearchRepository(store.connection),
            intelligence_repository=IntelligenceRepository(store.connection),
            loader=_loader(_market_record(liquidity="12000", volume="3000")),
            source_names=("coingecko",),
        )
        service.add("solana/PAIR123", now=NOW)

        result = service.scan(now=NOW)

    assert result.status == "OK"
    assert result.can_execute_trades is False
    assert result.scanned[0].pair_ref == "solana/PAIR123"
    assert result.scanned[0].can_execute_trades is False
    assert result.scanned[0].opportunity_score > 50


def test_watch_scan_creates_alert_when_risk_worsens() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        watch_repo = WatchlistRepository(store.connection)
        watch_repo.upsert_entry(pair_ref="solana/PAIR123", created_at=NOW)
        watch_repo.record_scan_result(
            WatchScanRecord(
                pair_ref="solana/PAIR123",
                scanned_at=NOW,
                status="OK",
                radar_state="WATCH",
                opportunity_score=50.0,
                risk_score=20.0,
                reason_codes=("PREVIOUS",),
            )
        )
        service = WatchlistService(
            watch_repo,
            research_repository=ResearchRepository(store.connection),
            intelligence_repository=IntelligenceRepository(store.connection),
            loader=_loader(_market_record(liquidity="500", volume="50")),
            source_names=("coingecko",),
        )

        result = service.scan(now=NOW)
        alerts = store.connection.execute("SELECT reason_codes_json FROM notification_alerts").fetchall()

    assert result.alerts_created
    assert "WATCH_RISK_WORSENED" in alerts[0][0]


def test_watch_scan_creates_alert_when_opportunity_improves() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        watch_repo = WatchlistRepository(store.connection)
        watch_repo.upsert_entry(pair_ref="solana/PAIR123", created_at=NOW)
        watch_repo.record_scan_result(
            WatchScanRecord(
                pair_ref="solana/PAIR123",
                scanned_at=NOW,
                status="OK",
                radar_state="WATCH",
                opportunity_score=35.0,
                risk_score=20.0,
                reason_codes=("PREVIOUS",),
            )
        )
        service = WatchlistService(
            watch_repo,
            research_repository=ResearchRepository(store.connection),
            intelligence_repository=IntelligenceRepository(store.connection),
            loader=_loader(_market_record(liquidity="12000", volume="3000")),
            source_names=("coingecko",),
        )

        result = service.scan(now=NOW)
        alerts = store.connection.execute("SELECT reason_codes_json FROM notification_alerts").fetchall()

    assert result.alerts_created
    assert "WATCH_OPPORTUNITY_IMPROVED" in alerts[0][0]


def _loader(record):
    return LiveMarketLoader.from_optional_transports(
        coingecko_transport=lambda _pair_ref: record,
        now=NOW,
    )


def _market_record(*, liquidity: str, volume: str):
    return {
        "pair_id": "PAIR123",
        "chain_id": "solana",
        "base_symbol": "BONK",
        "quote_symbol": "USDC",
        "price_usd": "0.01",
        "liquidity_usd": liquidity,
        "volume_24h_usd": volume,
        "observed_at": NOW.isoformat(),
        "source_record_id": "fixture-watch",
        "raw_status": "fixture",
    }
