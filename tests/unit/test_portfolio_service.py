from datetime import datetime, timezone
from decimal import Decimal

from portfolio.repository import PortfolioRepository
from portfolio.service import PortfolioService
from storage.duckdb_store import DuckDBStore
from storage.schema import initialize_schema

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_portfolio_service_add_list_remove_and_report() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        service = PortfolioService(PortfolioRepository(store.connection))

        entry = service.add(
            symbol="bonk",
            chain="solana",
            pair_ref="solana/BONK",
            entry_price=Decimal("0.001"),
            size_usd=Decimal("20"),
            thesis="meme momentum",
            stop_zone="below VWAP",
            take_profit_zone="2x",
            conviction="medium",
            risk_level="high",
            notes="manual only",
            now=NOW,
        )
        entries = service.list()
        report = service.report(now=NOW)
        removed = service.remove(entry.entry_id)

    assert entry.symbol == "BONK"
    assert entry.can_execute_trades is False
    assert entries[0].entry_id == entry.entry_id
    assert report.total_exposure_usd == Decimal("20.00000000")
    assert report.can_execute_trades is False
    assert removed is True


def test_portfolio_service_rejects_invalid_sizes() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        service = PortfolioService(PortfolioRepository(store.connection))

        try:
            service.add(
                symbol="BAD",
                entry_price=Decimal("0"),
                size_usd=Decimal("20"),
                thesis="bad",
            )
        except ValueError as exc:
            assert "entry_price" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected invalid entry price")
