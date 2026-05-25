from datetime import datetime, timezone

from data_pipeline.live_market_loader import LiveMarketLoader
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository, ResearchRepository
from storage.schema import initialize_schema, list_tables
from watchlist.repository import WatchlistRepository
from watchlist.service import WatchlistService

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_watchlist_tables_and_scan_persist_to_duckdb(tmp_path) -> None:
    database = tmp_path / "watchlist.duckdb"
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        tables = list_tables(store.connection)
        service = WatchlistService(
            WatchlistRepository(store.connection),
            research_repository=ResearchRepository(store.connection),
            intelligence_repository=IntelligenceRepository(store.connection),
            loader=LiveMarketLoader.from_optional_transports(
                coingecko_transport=lambda _pair_ref: _record(),
                now=NOW,
            ),
            source_names=("coingecko",),
        )
        service.add("solana/PAIR123", note="integration", tags=("test",), now=NOW)
        result = service.scan(now=NOW)
        entry_count = store.connection.execute("SELECT COUNT(*) FROM watchlist_entries").fetchone()[0]
        scan_count = store.connection.execute("SELECT COUNT(*) FROM watchlist_scan_results").fetchone()[0]
        evidence_count = store.connection.execute(
            "SELECT COUNT(*) FROM evidence_snapshots WHERE source_name LIKE 'market_scan:%'"
        ).fetchone()[0]

    assert "watchlist_entries" in tables
    assert "watchlist_scan_results" in tables
    assert result.status == "OK"
    assert entry_count == 1
    assert scan_count == 1
    assert evidence_count == 1


def _record():
    return {
        "pair_id": "PAIR123",
        "chain_id": "solana",
        "base_symbol": "BONK",
        "quote_symbol": "USDC",
        "price_usd": "0.01",
        "liquidity_usd": "12000",
        "volume_24h_usd": "3000",
        "observed_at": NOW.isoformat(),
        "source_record_id": "fixture-watch",
        "raw_status": "fixture",
    }
