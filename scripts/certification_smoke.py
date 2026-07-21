"""Create, migrate, back up, and restore a minimal local DuckDB database."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.schema import EXPECTED_TABLES, initialize_schema, list_tables


def main() -> int:
    with TemporaryDirectory(prefix="traidr-cert-") as directory:
        source = Path(directory) / "source.duckdb"
        backup = Path(directory) / "backup.duckdb"
        with duckdb.connect(str(source)) as connection:
            initialize_schema(connection)
            initialize_schema(connection)
            connection.execute("CHECKPOINT")
        backup.write_bytes(source.read_bytes())
        with duckdb.connect(str(backup), read_only=True) as restored:
            missing = EXPECTED_TABLES - list_tables(restored)
            if missing:
                raise RuntimeError(f"backup restore missing tables: {sorted(missing)}")
            integrity = restored.execute("SELECT count(*) FROM schema_migrations").fetchone()
            if integrity is None or integrity[0] < 1:
                raise RuntimeError("backup restore has no schema migration history")
    print("Migration and backup restore smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
