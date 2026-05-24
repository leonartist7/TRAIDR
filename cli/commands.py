"""Command implementations for the local TRAIDR operator CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from data_pipeline.scan_models import MarketScanCandidate
from agents.agent_bus import run_agent_bus
from agents.liquidity_agent import LiquidityAgent
from agents.technical_agent import TechnicalAgent
from agents.token_safety_agent import TokenSafetyAgent
from cli.formatters import bullet_list, key_values, records_table, section
from data_pipeline.market_scan import real_dexscreener_loader, scan_markets
from data_pipeline.token_discovery import default_dexscreener_discovery_transport, discover_tokens
from radar.discovery_to_radar import discovery_candidates_to_radar
from radar.scan_to_radar import scan_candidates_to_radar
from radar.opportunity_radar import rank_watchlist
from scheduler.reports import build_research_report
from scheduler.research_scheduler import ResearchScheduler
from scripts.run_simulation import run_simulation
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository, ResearchRepository
from storage.schema import initialize_schema, list_tables
from token_detail.detail_builder import build_token_detail
from token_detail.formatters import format_token_detail

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
    scan_candidates = [] if fixture else _latest_scan_candidates(db_path, limit)
    if scan_candidates:
        radar_rows = [candidate.to_dict() for candidate in scan_candidates_to_radar(scan_candidates)[:limit]]
        return CommandResult(
            0,
            section(
                "Opportunity Radar",
                ["source: scan_evidence", *records_table(radar_rows).splitlines()],
            ),
        )

    candidates = [candidate.to_dict() for candidate in _fixture_radar()]
    return CommandResult(
        0,
        section(
            "Opportunity Radar",
            ["source: fixture", *records_table(candidates).splitlines()],
        ),
    )


def scan(
    database: str | None = None,
    *,
    fixture: bool = False,
    source: str | None = None,
    pair_refs: tuple[str, ...] = (),
    limit: int = 10,
) -> CommandResult:
    if not fixture and source is None:
        return CommandResult(
            0,
            section(
                "Market Scan",
                [
                    "status: INSUFFICIENT_DATA",
                    "reason_codes: SCAN_SOURCE_REQUIRED",
                    "No candidates found.",
                    "Use `--fixture` for offline scan or `--source dexscreener --pair-ref <chain>/<pairAddress>` for read-only DexScreener scan.",
                ],
            ),
        )
    if not fixture and source != "dexscreener":
        return CommandResult(
            0,
            section(
                "Market Scan",
                [
                    "status: INSUFFICIENT_DATA",
                    f"reason_codes: SCAN_SOURCE_UNSUPPORTED:{source}",
                    "No candidates found.",
                    "Supported real read-only source: dexscreener.",
                ],
            ),
        )

    db_path = _database_path(database) if database else None
    repository: ResearchRepository | None = None
    store_context = DuckDBStore(db_path) if db_path is not None else None
    if store_context is not None:
        store = store_context.__enter__()
        initialize_schema(store.connection)
        repository = ResearchRepository(store.connection)
    try:
        result = scan_markets(
            fixture=fixture,
            pair_refs=pair_refs,
            source_names=(source,) if source else ("dexscreener", "coingecko", "defillama"),
            loader=real_dexscreener_loader() if source == "dexscreener" else None,
            repository=repository,
        )
    finally:
        if store_context is not None:
            store_context.__exit__(None, None, None)

    if not result.candidates:
        return CommandResult(
            0,
            section(
                "Market Scan",
                [
                    f"status: {result.status}",
                    f"reason_codes: {', '.join(result.reason_codes)}",
                    "No candidates found.",
                ],
            ),
        )

    rows = [candidate.to_dict() for candidate in result.candidates[:limit]]
    radar_rows = [candidate.to_dict() for candidate in scan_candidates_to_radar(result.candidates)[:limit]]
    return CommandResult(
        0,
        "\n\n".join(
            (
                section(
                    "Market Scan",
                    [
                        f"status: {result.status}",
                        f"reason_codes: {', '.join(result.reason_codes)}",
                        f"database: {db_path or 'not persisted'}",
                    ],
                ),
                section("Scan Candidates", records_table(rows).splitlines()),
                section("Radar From Scan", records_table(radar_rows).splitlines()),
            )
        ),
    )


def discover(
    database: str | None = None,
    *,
    fixture: bool = False,
    source: str | None = None,
    limit: int = 20,
) -> CommandResult:
    if not fixture and source != "dexscreener":
        return CommandResult(
            0,
            section(
                "Token Discovery",
                [
                    "status: INSUFFICIENT_DATA",
                    "reason_codes: DISCOVERY_SOURCE_REQUIRED",
                    "No candidates found.",
                    "Use `--fixture` for offline discovery or `--source dexscreener` for read-only DexScreener discovery.",
                ],
            ),
        )
    db_path = _database_path(database) if database else None
    repository: ResearchRepository | None = None
    store_context = DuckDBStore(db_path) if db_path is not None else None
    if store_context is not None:
        store = store_context.__enter__()
        initialize_schema(store.connection)
        repository = ResearchRepository(store.connection)
    try:
        result = discover_tokens(
            fixture=fixture,
            source=source,
            limit=limit,
            transport=default_dexscreener_discovery_transport if source == "dexscreener" else None,
            repository=repository,
        )
    finally:
        if store_context is not None:
            store_context.__exit__(None, None, None)

    if not result.candidates:
        return CommandResult(
            0,
            section(
                "Token Discovery",
                [
                    f"status: {result.status}",
                    f"reason_codes: {', '.join(result.reason_codes)}",
                    "No candidates found.",
                ],
            ),
        )
    rows = [candidate.to_dict() for candidate in result.candidates[:limit]]
    radar_rows = [candidate.to_dict() for candidate in discovery_candidates_to_radar(result.candidates)[:limit]]
    return CommandResult(
        0,
        "\n\n".join(
            (
                section(
                    "Token Discovery",
                    [
                        f"status: {result.status}",
                        f"reason_codes: {', '.join(result.reason_codes)}",
                        f"database: {db_path or 'not persisted'}",
                    ],
                ),
                section("Discovery Candidates", records_table(rows).splitlines()),
                section("Radar From Discovery", records_table(radar_rows).splitlines()),
            )
        ),
    )


def token_detail(
    database: str | None = None,
    *,
    fixture: bool = False,
    pair_ref: str | None = None,
    source: str | None = None,
) -> CommandResult:
    if not fixture and (source != "dexscreener" or not pair_ref):
        report = build_token_detail()
        return CommandResult(0, format_token_detail(report))

    db_path = _database_path(database) if database else None
    repository: ResearchRepository | None = None
    store_context = DuckDBStore(db_path) if db_path is not None else None
    if store_context is not None:
        store = store_context.__enter__()
        initialize_schema(store.connection)
        repository = ResearchRepository(store.connection)
    try:
        report = build_token_detail(
            fixture=fixture,
            pair_ref=pair_ref,
            source=source,
            repository=repository,
        )
    finally:
        if store_context is not None:
            store_context.__exit__(None, None, None)
    return CommandResult(0, format_token_detail(report))


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


def _latest_scan_candidates(database: Path, limit: int) -> tuple[MarketScanCandidate, ...]:
    if not database.exists():
        return ()
    with DuckDBStore(database, read_only=True) as store:
        tables = list_tables(store.connection)
        if "evidence_snapshots" not in tables:
            return ()
        rows = store.execute(
            """
            SELECT payload_json
            FROM evidence_snapshots
            WHERE source_name LIKE 'market_scan:%'
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()
    candidates: list[MarketScanCandidate] = []
    for (payload_json,) in rows:
        try:
            payload = json.loads(payload_json)
            candidates.append(
                MarketScanCandidate(
                    token_pair_id=str(payload.get("token_pair_id") or payload["pair_id"]),
                    source=str(payload["source"]),
                    observed_at=datetime.fromisoformat(str(payload["observed_at"])),
                    price_usd=_decimal_or_none(payload.get("price_usd")),
                    liquidity_usd=_decimal_or_none(payload.get("liquidity_usd")),
                    volume_24h_usd=_decimal_or_none(payload.get("volume_24h_usd")),
                    data_quality=str(payload["data_quality"]),
                    reason_codes=tuple(payload.get("reason_codes") or ("SCAN_EVIDENCE_LOADED",)),
                    snapshot=None,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(candidates)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


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
