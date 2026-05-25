from decimal import Decimal

from portfolio.repository import PortfolioRepository
from portfolio.service import PortfolioService
from storage.duckdb_store import DuckDBStore
from storage.schema import initialize_schema, list_tables


def test_manual_portfolio_persists_to_duckdb(tmp_path) -> None:
    database = tmp_path / "manual-portfolio.duckdb"
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        service = PortfolioService(PortfolioRepository(store.connection))
        entry = service.add(
            symbol="SOL",
            chain="solana",
            pair_ref="solana/SOL",
            entry_price=Decimal("100"),
            size_usd=Decimal("20"),
            thesis="manual exposure test",
        )
        tables = list_tables(store.connection)
        count = store.connection.execute("SELECT COUNT(*) FROM manual_portfolio_entries").fetchone()[0]
        row = store.connection.execute(
            "SELECT symbol, active FROM manual_portfolio_entries WHERE entry_id = ?",
            [entry.entry_id],
        ).fetchone()

    assert "manual_portfolio_entries" in tables
    assert count == 1
    assert row == ("SOL", True)
