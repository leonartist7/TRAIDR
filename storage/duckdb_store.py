"""DuckDB connection lifecycle helpers for local TRAIDR storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


class DuckDBStore:
    """Own a local DuckDB connection without hiding schema setup side effects."""

    def __init__(self, database: str | Path = ":memory:", *, read_only: bool = False) -> None:
        self.database = str(database)
        self.read_only = read_only
        self._connection: duckdb.DuckDBPyConnection | None = None

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            self._connection = self._connect()
        return self._connection

    def execute(self, query: str, parameters: Any = None) -> duckdb.DuckDBPyConnection:
        if parameters is None:
            return self.connection.execute(query)
        return self.connection.execute(query, parameters)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "DuckDBStore":
        self.connection
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        if self.database != ":memory:" and not self.database.startswith(":memory:"):
            database_path = Path(self.database)
            if not self.read_only:
                database_path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(database=self.database, read_only=self.read_only)

