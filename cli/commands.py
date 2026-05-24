"""Command implementations for the local TRAIDR operator CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.agent_bus import run_agent_bus
from agents.liquidity_agent import LiquidityAgent
from agents.technical_agent import TechnicalAgent
from agents.token_safety_agent import TokenSafetyAgent
from cli.formatters import bullet_list, key_values, records_table, section
from radar.opportunity_radar import rank_watchlist
from scheduler.reports import build_research_report
from scheduler.research_scheduler import ResearchScheduler
from scripts.run_simulation import run_simulation
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository
from storage.schema import initialize_schema, list_tables

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / "config" / "settings.yaml"
DASHBOARD_COMMAND = "python -m streamlit run dashboard/app.py"


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    output: str


def status(database: str | None = None) -> CommandResult:
    settings = _load_settings()
    db_path = _database_path(database)
    db_exists = db_path.exists()
    table_count = 0
    if db_exists:
        with DuckDBStore(db_path, read_only=True) as store:
            table_count = len(list_tables(store.connection))
    output = section(
        "TRAIDR Status",
        key_values(
            {
                "project": settings["project"]["name"],
                "mode": settings["runtime"]["mode"],
                "local_only": settings["runtime"]["local_only"],
                "live_trading": settings["runtime"]["live_trading_implemented"],
                "withdrawals": settings["runtime"]["withdrawals_implemented"],
                "database": db_path,
                "database_exists": db_exists,
                "tables": table_count,
            }
        ).splitlines(),
    )
    return CommandResult(0, output)


def simulate(database: str | None = None, *, memory: bool = False) -> CommandResult:
    target = ":memory:" if memory else str(_database_path(database))
    summary = run_simulation(target)
    output = section(
        "TRAIDR Simulation",
        key_values(
            {
                "mode": summary["mode"],
                "database": summary["database"],
                "pair": summary["pair_id"],
                "intent": summary["intent"],
                "risk": f"{summary['risk_status']} ({', '.join(summary['risk_reasons'])})",
                "execution": f"{summary['execution_status']} ({', '.join(summary['execution_reasons'])})",
                "paper_fill_id": summary["fill_id"],
                "orders": summary["stored_orders"],
                "fills": summary["stored_fills"],
                "audit_events": summary["stored_audit_events"],
            }
        ).splitlines(),
    )
    return CommandResult(0 if summary["ok"] else 1, output)


def inspect(database: str | None = None, *, limit: int = 5) -> CommandResult:
    db_path = _database_path(database)
    if not db_path.exists():
        return CommandResult(0, f"No local DuckDB database found at {db_path}. Run `traidr simulate` first.")
    with DuckDBStore(db_path, read_only=True) as store:
        tables = list_tables(store.connection)
        blocks = [
            section("TRAIDR Inspect", [f"database: {db_path}", "tables:", *[f"- {table}" for table in sorted(tables)]]),
            _latest_block(store, tables, "audit_events", limit),
            _latest_block(store, tables, "simulated_orders", limit),
            _latest_block(store, tables, "simulated_fills", limit),
        ]
    return CommandResult(0, "\n\n".join(blocks))


def radar(database: str | None = None, *, fixture: bool = False, limit: int = 10) -> CommandResult:
    db_path = _database_path(database)
    records = [] if fixture else _query_records(db_path, "opportunity_radar_states", limit)
    if records:
        return CommandResult(0, section("Opportunity Radar", records_table(records).splitlines()))

    candidates = [candidate.to_dict() for candidate in _fixture_radar()]
    return CommandResult(
        0,
        section(
            "Opportunity Radar",
            ["source: fixture", *records_table(candidates).splitlines()],
        ),
    )


def report(database: str | None = None, *, report_type: str = "daily", limit: int = 5) -> CommandResult:
    db_path = _database_path(database)
    rows = _query_records(
        db_path,
        "research_reports",
        limit,
        where="report_type = ?",
        params=[report_type],
    )
    if rows:
        return CommandResult(0, section("Research Reports", records_table(rows).splitlines()))
    fixture = build_research_report(
        report_type=report_type,
        radar_states=[candidate.to_dict() for candidate in _fixture_radar()],
    )
    return CommandResult(
        0,
        section("Research Reports", ["source: fixture", *key_values(fixture).splitlines()]),
    )


def alerts(database: str | None = None, *, limit: int = 10) -> CommandResult:
    db_path = _database_path(database)
    rows = _query_records(db_path, "notification_alerts", limit)
    return CommandResult(0, section("Local Alerts", records_table(rows, empty="No local alert history found.").splitlines()))


def dashboard(database: str | None = None) -> CommandResult:
    db_path = _database_path(database)
    return CommandResult(
        0,
        section(
            "TRAIDR Dashboard",
            [
                "Dashboard launch is manual for safety.",
                f"database: {db_path}",
                f"command: {DASHBOARD_COMMAND}",
            ],
        ),
    )


def scheduler_once(database: str | None = None) -> CommandResult:
    db_path = _database_path(database)
    with DuckDBStore(db_path) as store:
        initialize_schema(store.connection)
        repository = IntelligenceRepository(store.connection)
        scheduler = ResearchScheduler(repository=repository, handlers=_scheduler_handlers())
        now = datetime.now(timezone.utc)
        last_runs = _latest_scheduler_runs(store)
        results = scheduler.run_due_tasks(now=now, context={}, last_runs=last_runs)
        for result in results:
            report_type = _report_type_for_task(result.task_name)
            if report_type is not None:
                repository.record_research_report(
                    report_type=report_type,
                    status=result.status,
                    reason_codes=result.reason_codes,
                    payload=result.to_dict(),
                    recorded_at=now,
                )
    return CommandResult(
        0,
        section(
            "Scheduler Once",
            [
                f"database: {db_path}",
                f"tasks_run: {len(results)}",
                *bullet_list(
                    f"{result.task_name}: {result.status} ({', '.join(result.reason_codes)})"
                    for result in results
                ).splitlines(),
            ],
        ),
    )


def _load_settings() -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError:
        return {
            "project": {"name": "traidr"},
            "runtime": {
                "mode": "simulation",
                "local_only": True,
                "live_trading_implemented": False,
                "withdrawals_implemented": False,
            },
            "storage": {"local_database_path": "data/traidr.duckdb"},
        }
    with SETTINGS_PATH.open(encoding="utf-8") as settings_file:
        return yaml.safe_load(settings_file)


def _database_path(database: str | None = None) -> Path:
    configured = database or _load_settings()["storage"]["local_database_path"]
    path = Path(configured)
    return path if path.is_absolute() else ROOT / path


def _latest_block(store: DuckDBStore, tables: set[str], table: str, limit: int) -> str:
    rows = _query_table(store, tables, table, limit)
    return section(f"Latest {table}", records_table(rows, empty="- no rows").splitlines())


def _query_records(
    database: Path,
    table: str,
    limit: int,
    *,
    where: str | None = None,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    if not database.exists():
        return []
    with DuckDBStore(database, read_only=True) as store:
        tables = list_tables(store.connection)
        if table not in tables:
            return []
        query = f"SELECT * FROM {table}"
        parameters = params or []
        if where:
            query = f"{query} WHERE {where}"
        query = f"{query} ORDER BY 2 DESC LIMIT ?"
        return _rows_to_dicts(store.execute(query, [*parameters, limit]))


def _query_table(store: DuckDBStore, tables: set[str], table: str, limit: int) -> list[dict[str, Any]]:
    if table not in tables:
        return []
    return _rows_to_dicts(store.execute(f"SELECT * FROM {table} ORDER BY 2 DESC LIMIT ?", [limit]))


def _rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [_normalize_row(dict(zip(columns, row))) for row in cursor.fetchall()]


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if key.endswith("_json") and isinstance(value, str):
            try:
                normalized[key] = json.dumps(json.loads(value), separators=(",", ":"))
            except json.JSONDecodeError:
                normalized[key] = value
        else:
            normalized[key] = value
    return normalized


def _fixture_radar():
    analyses = run_agent_bus(
        [TechnicalAgent(), LiquidityAgent(), TokenSafetyAgent()],
        {"technical_momentum": 0.7, "liquidity_usd": 15000, "token_safety_clear": True},
    ).analyses
    return rank_watchlist([{"subject_id": "fixture-sol-usdc", "analyses": analyses}])


def _scheduler_handlers():
    return {
        "watchlist_check": lambda _context: {"status": "OK", "reason_codes": ["WATCHLIST_CHECKED"]},
        "technical_update": lambda _context: {"status": "OK", "reason_codes": ["TECHNICAL_UPDATE_COMPLETE"]},
        "radar_update": lambda _context: {
            "status": "OK",
            "reason_codes": ["RADAR_UPDATE_COMPLETE"],
            "radar": [candidate.to_dict() for candidate in _fixture_radar()],
        },
        "macro_news_update": lambda _context: {"status": "OK", "reason_codes": ["MACRO_NEWS_LOCAL_ONLY"]},
        "opportunity_report": lambda _context: build_research_report(
            report_type="4h",
            radar_states=[candidate.to_dict() for candidate in _fixture_radar()],
        ),
        "daily_report": lambda _context: build_research_report(
            report_type="daily",
            radar_states=[candidate.to_dict() for candidate in _fixture_radar()],
        ),
    }


def _report_type_for_task(task_name: str) -> str | None:
    if task_name == "opportunity_report":
        return "4h"
    if task_name == "daily_report":
        return "daily"
    return None


def _latest_scheduler_runs(store: DuckDBStore) -> dict[str, datetime | None]:
    tables = list_tables(store.connection)
    if "scheduler_runs" not in tables:
        return {}
    rows = store.execute(
        """
        SELECT task_name, MAX(recorded_at)
        FROM scheduler_runs
        GROUP BY task_name
        """
    ).fetchall()
    return {row[0]: row[1].replace(tzinfo=timezone.utc) if row[1] else None for row in rows}
