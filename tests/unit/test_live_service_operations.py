import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from config.runtime_settings import load_research_settings
from data_pipeline.coingecko_adapter import CoinGeckoAdapter
from scheduler.live_service import LiveResearchService
from storage.duckdb_store import DuckDBStore
from storage.market_repository import MarketRepository
from storage.schema import initialize_schema


def test_service_checkpoint_backup_stays_in_configured_directory(tmp_path: Path) -> None:
    database_path = tmp_path / "traidr.duckdb"
    settings = load_research_settings("live_public")
    service_settings = settings.service.model_copy(
        update={
            "database_path": database_path,
            "backup_directory": tmp_path / "backups",
            "log_path": tmp_path / "logs" / "service.jsonl",
        }
    )
    service = LiveResearchService(
        settings.model_copy(update={"service": service_settings}),
        database_path=database_path,
    )
    with DuckDBStore(database_path) as store:
        initialize_schema(store.connection)
        backup = service._create_backup(MarketRepository(store.connection))

    assert backup.exists()
    assert backup.parent == (tmp_path / "backups").resolve()
    assert backup.name.startswith("traidr-")


def test_cross_market_uses_normalized_snapshot_contract(tmp_path: Path) -> None:
    observed_at = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    settings = load_research_settings("live_public")
    service_settings = settings.service.model_copy(
        update={"database_path": tmp_path / "traidr.duckdb"}
    )
    service = LiveResearchService(settings.model_copy(update={"service": service_settings}))
    service.coingecko = CoinGeckoAdapter(
        lambda coin_id: {
            "id": coin_id,
            "symbol": "btc",
            "market_data": {
                "current_price": {"usd": "100"},
                "total_value_locked": {"usd": "1000000"},
                "total_volume": {"usd": "2000000"},
            },
            "last_updated": observed_at.isoformat(),
        },
        now=observed_at,
    )

    result = asyncio.run(service._cross_market("asset:bitcoin", Decimal("101")))

    assert result is not None
    assert result["spot_price_usd"] == "100"
    assert result["divergence_bps"] == 100.0
    assert result["observed_at"] == observed_at.isoformat()
