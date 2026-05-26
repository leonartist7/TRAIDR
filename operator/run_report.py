"""Formatting helpers for the local daily run report."""

from __future__ import annotations

from typing import Any


def build_run_report(
    *,
    database: str,
    status: dict[str, Any],
    scanned: dict[str, Any],
    watchlist: dict[str, Any],
    top_opportunities: list[dict[str, Any]],
    top_risks: list[dict[str, Any]],
    alerts_generated: int,
    missing_data: list[str],
    next_commands: list[str],
    report_id: str | None,
) -> dict[str, Any]:
    return {
        "database": database,
        "status": status,
        "scanned": scanned,
        "watchlist": watchlist,
        "top_opportunities": top_opportunities,
        "top_risks": top_risks,
        "alerts_generated": alerts_generated,
        "missing_data": missing_data,
        "next_suggested_commands": next_commands,
        "report_id": report_id,
        "can_execute_trades": False,
    }


def format_run_report(report: dict[str, Any]) -> str:
    sections = [
        _section(
            "TRAIDR Daily Run",
            [
                f"database: {report['database']}",
                f"mode: {report['status'].get('mode')}",
                f"live_trading: {report['status'].get('live_trading')}",
                f"withdrawals: {report['status'].get('withdrawals')}",
                f"can_execute_trades: {report['can_execute_trades']}",
                f"report_id: {report.get('report_id') or 'not_recorded'}",
            ],
        ),
        _section("What Was Scanned", _dict_lines(report["scanned"])),
        _section("Watchlist Update", _dict_lines(report["watchlist"])),
        _section("Top Opportunities", _row_lines(report["top_opportunities"], "No opportunities found.")),
        _section("Top Risks", _row_lines(report["top_risks"], "No risk rows found.")),
        _section("Alerts Generated", [str(report["alerts_generated"])]),
        _section("Missing Data", _list_lines(report["missing_data"], "No missing data warnings.")),
        _section("Next Suggested Commands", _list_lines(report["next_suggested_commands"], "No next commands suggested.")),
        _section("No Execution Actions", ["Daily run is read-only research and cannot execute trades."]),
    ]
    return "\n\n".join(sections)


def _section(title: str, lines: list[str]) -> str:
    return "\n".join((title, "-" * len(title), *lines))


def _dict_lines(values: dict[str, Any]) -> list[str]:
    return [f"{key}: {value}" for key, value in values.items()]


def _row_lines(rows: list[dict[str, Any]], empty: str) -> list[str]:
    if not rows:
        return [empty]
    lines = []
    for row in rows:
        subject = row.get("subject_id") or row.get("token_pair_id") or "unknown"
        state = row.get("state", "unknown")
        opportunity = row.get("opportunity_score", "unknown")
        risk = row.get("risk_score", "unknown")
        lines.append(f"- {subject}: state={state}; opportunity={opportunity}; risk={risk}; can_execute_trades=false")
    return lines


def _list_lines(values: list[str], empty: str) -> list[str]:
    return [f"- {value}" for value in values] if values else [empty]
