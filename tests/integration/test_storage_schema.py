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

