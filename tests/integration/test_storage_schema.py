from storage.duckdb_store import DuckDBStore
from storage.schema import EXPECTED_TABLES, SCHEMA_VERSION, initialize_schema, list_tables


def test_duckdb_schema_initializes_in_memory() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)

        assert EXPECTED_TABLES <= list_tables(store.connection)
        version = store.connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchone()

    assert version == (SCHEMA_VERSION,)


def test_schema_v8_upgrades_additively_to_shadow_evidence_without_losing_scanner_rows() -> None:
    with DuckDBStore(":memory:") as store:
        initialize_schema(store.connection)
        store.connection.execute(
            """
            INSERT INTO market_scanner_scores VALUES (
                'legacy-score', 'bitunix:BTCUSDT', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                'NO_TRADE', 'NO_TRADE', NULL, NULL, NULL, NULL, '[]', '[]', '[]', FALSE
            )
            """
        )
        store.connection.execute("DROP TABLE shadow_market_evidence")
        store.connection.execute("DELETE FROM schema_migrations WHERE version = ?", [SCHEMA_VERSION])
        store.connection.execute(
            "INSERT INTO schema_migrations VALUES (8, CURRENT_TIMESTAMP) ON CONFLICT DO NOTHING"
        )

        initialize_schema(store.connection)

        assert "shadow_market_evidence" in list_tables(store.connection)
        assert store.connection.execute(
            "SELECT COUNT(*) FROM market_scanner_scores WHERE score_id = 'legacy-score'"
        ).fetchone() == (1,)
        assert store.connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone() == (SCHEMA_VERSION,)
