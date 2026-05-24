from datetime import datetime, timezone

from data_pipeline.live_market_loader import LiveMarketLoader
from data_pipeline.market_scan import scan_markets
from storage.duckdb_store import DuckDBStore
from storage.repositories import ResearchRepository
from storage.schema import initialize_schema


def test_fixture_scan_returns_read_only_candidates() -> None:
    result = scan_markets(fixture=True)

    assert result.status == "OK"
    assert result.can_execute_trades is False
    assert result.candidates
    assert result.candidates[0].token_pair_id == "fixture-sol-usdc"
    assert result.candidates[0].can_execute_trades is False
    assert result.candidates[0].data_quality == "sufficient"


def test_real_source_scan_without_sources_fails_closed() -> None:
    result = scan_markets(pair_refs=("sol-usdc",), loader=LiveMarketLoader())

    assert result.status == "INSUFFICIENT_DATA"
    assert result.candidates == ()
    assert "SOURCE_UNAVAILABLE" in result.reason_codes


def test_scan_stores_candidates_as_research_evidence(tmp_path) -> None:
    database = tmp_path / "scan.duckdb"
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        repository = ResearchRepository(store.connection)
        result = scan_markets(fixture=True, repository=repository)
        count = store.connection.execute(
            "SELECT COUNT(*) FROM evidence_snapshots WHERE source_name LIKE 'market_scan:%'"
        ).fetchone()[0]

    assert result.status == "OK"
    assert count == len(result.candidates)


def test_raw_scan_missing_data_returns_insufficient_data() -> None:
    result = scan_markets(
        raw_records=[{"pair_id": "bad"}],
        now=datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
    )

    assert result.status == "INSUFFICIENT_DATA"
    assert "MARKET_SOURCE_FIELDS_MISSING" in result.reason_codes

