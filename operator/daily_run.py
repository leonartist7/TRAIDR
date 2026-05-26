"""Local daily research workflow for TRAIDR."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from alerts.rules import ResearchAlertSnapshot
from alerts.rule_engine import ResearchAlertRuleEngine
from data_pipeline.market_scan import fixture_loader, scan_markets
from notifications.dedupe import AlertDeduper
from notifications.dispatcher import NotificationDispatcher
from notifications.history import AlertHistory
from radar.models import RadarCandidate
from radar.scan_to_radar import scan_candidates_to_radar
from reports.daily_briefing import build_daily_briefing
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository, ResearchRepository
from storage.schema import initialize_schema, list_tables
from watchlist.repository import WatchlistRepository
from watchlist.service import WatchlistService


def run_daily_research(
    *,
    database_path: str | Path,
    fixture_scan: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run the local read-only research workflow and persist a report."""

    run_at = now or datetime.now(timezone.utc)
    database = Path(database_path)
    if database != Path(":memory:") and database.parent:
        database.parent.mkdir(parents=True, exist_ok=True)

    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        tables = list_tables(store.connection)
        research = ResearchRepository(store.connection)
        intelligence = IntelligenceRepository(store.connection)
        status = _status(tables)
        scan_result = scan_markets(fixture=fixture_scan, repository=research, now=run_at)
        radar_rows = _persist_radar(scan_candidates_to_radar(scan_result.candidates), intelligence, run_at)
        watchlist_result = _update_watchlist(store, research, intelligence, run_at)
        alerts_generated = _generate_alerts(radar_rows, intelligence, store, run_at)
        briefing = build_daily_briefing(store.connection, now=run_at)
        missing = list(dict.fromkeys([*briefing.missing_data_warnings, *([] if scan_result.candidates else ["NO_SCAN_CANDIDATES"])]))
        report = _report_module().build_run_report(
            database=str(database),
            status=status,
            scanned={
                "status": scan_result.status,
                "candidate_count": len(scan_result.candidates),
                "reason_codes": list(scan_result.reason_codes),
                "fixture_scan": fixture_scan,
                "can_execute_trades": False,
            },
            watchlist=watchlist_result,
            top_opportunities=briefing.top_radar_candidates[:5],
            top_risks=briefing.highest_risk_candidates[:5],
            alerts_generated=alerts_generated + int(watchlist_result.get("alerts_created", 0)),
            missing_data=missing,
            next_commands=list(briefing.next_commands or _default_next_commands(str(database))),
            report_id=None,
        )
        report_id = intelligence.record_research_report(
            report_type="daily_run",
            status=briefing.state.value,
            reason_codes=("DAILY_RUN_COMPLETE", "NO_EXECUTION_ACTION", *briefing.reason_codes),
            payload=report,
            recorded_at=run_at,
        )
        report["report_id"] = report_id
        return report


def format_daily_run_report(report: dict[str, Any]) -> str:
    return _report_module().format_run_report(report)


def _persist_radar(
    candidates: tuple[RadarCandidate, ...],
    repository: IntelligenceRepository,
    recorded_at: datetime,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        payload = candidate.to_dict()
        repository.record_radar_state(
            subject_id=candidate.subject_id,
            state=candidate.state.value,
            rank=candidate.rank,
            opportunity_score=candidate.opportunity_score,
            risk_score=candidate.risk_score,
            confidence=candidate.confidence,
            reason_codes=candidate.reason_codes,
            payload=payload,
            recorded_at=recorded_at,
        )
        rows.append(payload)
    return rows


def _update_watchlist(
    store: DuckDBStore,
    research: ResearchRepository,
    intelligence: IntelligenceRepository,
    now: datetime,
) -> dict[str, Any]:
    tables = list_tables(store.connection)
    if "watchlist_entries" not in tables:
        return {"status": "INSUFFICIENT_DATA", "entries_scanned": 0, "alerts_created": 0, "reason_codes": ["WATCHLIST_TABLE_MISSING"], "can_execute_trades": False}
    service = WatchlistService(
        WatchlistRepository(store.connection),
        research_repository=research,
        intelligence_repository=intelligence,
        loader=fixture_loader(now),
        source_names=("coingecko", "defillama"),
    )
    result = service.scan(now=now)
    return {
        "status": result.status,
        "entries_scanned": len(result.scanned),
        "alerts_created": len(result.alerts_created),
        "reason_codes": list(result.reason_codes),
        "can_execute_trades": result.can_execute_trades,
    }


def _generate_alerts(
    radar_rows: list[dict[str, Any]],
    repository: IntelligenceRepository,
    store: DuckDBStore,
    now: datetime,
) -> int:
    dispatcher = NotificationDispatcher(
        history=AlertHistory(repository),
        deduper=AlertDeduper(_existing_alert_fingerprints(store)),
    )
    engine = ResearchAlertRuleEngine(dispatcher)
    total = 0
    for row in radar_rows:
        current = ResearchAlertSnapshot(
            subject_id=str(row["subject_id"]),
            state=str(row["state"]),
            opportunity_score=float(row["opportunity_score"]),
            risk_score=float(row["risk_score"]),
            liquidity_usd=None,
            data_quality="sufficient",
            safety_complete=False if float(row["risk_score"]) >= 70 else True,
            reason_codes=tuple(str(reason) for reason in row.get("reason_codes", ())),
        )
        total += engine.evaluate_and_dispatch(previous=None, current=current, now=now).alerts_created
    return total


def _status(tables: set[str]) -> dict[str, Any]:
    return {
        "mode": "simulation",
        "local_only": True,
        "live_trading": False,
        "withdrawals": False,
        "tables": len(tables),
        "can_execute_trades": False,
    }


def _existing_alert_fingerprints(store: DuckDBStore) -> tuple[str, ...]:
    if "notification_alerts" not in list_tables(store.connection):
        return ()
    rows = store.execute("SELECT DISTINCT fingerprint FROM notification_alerts").fetchall()
    return tuple(str(row[0]) for row in rows)


def _default_next_commands(database: str) -> tuple[str, ...]:
    return (
        f"python -m cli.main radar --database {database}",
        f"python -m cli.main briefing --database {database}",
        f"python -m cli.main alerts --database {database}",
    )


def _report_module():
    path = Path(__file__).with_name("run_report.py")
    spec = importlib.util.spec_from_file_location("_traidr_operator_run_report", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load daily run report helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
