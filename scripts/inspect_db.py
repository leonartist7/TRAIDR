"""Inspect local TRAIDR DuckDB paper records without mutating them."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.duckdb_store import DuckDBStore
from storage.schema import list_tables

SETTINGS_PATH = ROOT / "config" / "settings.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local TRAIDR DuckDB paper records.")
    parser.add_argument(
        "--database",
        help="DuckDB path override; defaults to config/settings.yaml storage path.",
    )
    args = parser.parse_args()
    database = Path(args.database) if args.database else _configured_database_path()
    database = database if database.is_absolute() else ROOT / database

    if not database.exists():
        print(f"No local DuckDB database found at {database}.")
        return 0

    with DuckDBStore(database, read_only=True) as store:
        tables = list_tables(store.connection)
        print(f"TRAIDR DuckDB: {database}")
        print("Tables:")
        for table in sorted(tables):
            print(f"- {table}")
        _print_latest(
            store,
            tables,
            "audit_events",
            """
            SELECT recorded_at, event_type, severity, reason_codes_json
            FROM audit_events
            ORDER BY recorded_at DESC
            LIMIT 5
            """,
        )
        _print_latest(
            store,
            tables,
            "simulated_orders",
            """
            SELECT created_at, side, pair_id, notional_usd, order_status
            FROM simulated_orders
            ORDER BY created_at DESC
            LIMIT 5
            """,
        )
        _print_latest(
            store,
            tables,
            "simulated_fills",
            """
            SELECT filled_at, order_id, quantity, price_usd, notional_usd
            FROM simulated_fills
            ORDER BY filled_at DESC
            LIMIT 5
            """,
        )
    return 0


def _configured_database_path() -> Path:
    with SETTINGS_PATH.open(encoding="utf-8") as settings_file:
        settings = yaml.safe_load(settings_file)
    return Path(settings["storage"]["local_database_path"])


def _print_latest(store: DuckDBStore, tables: set[str], table: str, query: str) -> None:
    print(f"Latest {table}:")
    if table not in tables:
        print("- table not initialized")
        return
    rows = store.execute(query).fetchall()
    if not rows:
        print("- no rows")
        return
    for row in rows:
        print(f"- {row}")


if __name__ == "__main__":
    raise SystemExit(main())
