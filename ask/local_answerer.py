"""Local DuckDB answerer for Ask TRAIDR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ask.intents import AskIntent, SUGGESTED_QUESTIONS
from ask.query_parser import parse_question
from dashboard.queries import DashboardData, configured_database_path, load_dashboard_data


def answer_local_question(
    question: str,
    *,
    database_path: str | Path | None = None,
    limit: int = 5,
) -> str:
    """Answer supported local questions without an external LLM."""

    intent = parse_question(question)
    data = load_dashboard_data(database_path, limit=limit)
    lines = [
        "Ask TRAIDR",
        "----------",
        f"question: {question}",
        f"intent: {intent.value}",
        "can_execute_trades: false",
        "",
    ]
    if not data.database_exists:
        lines.extend(_missing_database(data))
        return "\n".join(lines)
    lines.extend(_answer_intent(intent, data, limit))
    return "\n".join(lines)


def _answer_intent(intent: AskIntent, data: DashboardData, limit: int) -> list[str]:
    if intent is AskIntent.TOP_RISKS:
        rows = sorted(data.market_radar, key=lambda row: float(row.get("risk_score") or 0), reverse=True)[:limit]
        if not rows:
            return ["No radar risk rows found.", "Try: python -m cli.main scan --fixture --database <db>"]
        return ["Top Risks:", *_format_rows(rows, ("subject_id", "state", "risk_score", "reason_codes_json"))]
    if intent is AskIntent.TOP_OPPORTUNITIES:
        rows = sorted(data.market_radar, key=lambda row: float(row.get("opportunity_score") or 0), reverse=True)[:limit]
        if not rows:
            return ["No radar opportunity rows found.", "Try: python -m cli.main radar --fixture"]
        return ["Top Opportunities:", *_format_rows(rows, ("subject_id", "state", "opportunity_score", "confidence"))]
    if intent is AskIntent.RECENT_ALERTS:
        if not data.alerts:
            return ["No recent local alerts found."]
        return ["Recent Alerts:", *_format_rows(data.alerts[:limit], ("subject_id", "severity", "status", "reason_codes_json"))]
    if intent is AskIntent.PORTFOLIO_SUMMARY:
        exposure = sum(float(row.get("size_usd") or 0) for row in data.portfolio_entries)
        return [
            "Portfolio Summary:",
            f"active/manual rows: {len(data.portfolio_entries)}",
            f"total listed exposure usd: {exposure:.2f}",
            *_format_rows(data.portfolio_entries[:limit], ("symbol", "chain", "pair_ref", "size_usd", "risk_level")),
        ]
    if intent is AskIntent.SAFETY_STATUS:
        return ["Safety Status:", *_format_key_values(data.safety_status)]
    if intent is AskIntent.SCAN_SUMMARY:
        return [
            "Scan Summary:",
            f"scan rows: {len(data.scan_evidence)}",
            *_format_rows(data.scan_evidence[:limit], ("source_name", "quality_status", "observed_at", "payload_json")),
        ]
    return [
        "I can answer local TRAIDR database questions, but I did not recognize this one.",
        "Try one of:",
        *[f"- {question}" for question in SUGGESTED_QUESTIONS],
    ]


def _missing_database(data: DashboardData) -> list[str]:
    path = data.database_path if data.database_path else configured_database_path()
    return [
        f"No local DuckDB database found at {path}.",
        "Try:",
        f"python -m cli.main scan --fixture --database {path}",
        f"python -m cli.main scheduler-once --database {path}",
        f"python -m cli.main ask \"show scan summary\" --database {path}",
    ]


def _format_rows(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[str]:
    formatted: list[str] = []
    for row in rows:
        pieces = [f"{key}={row.get(key)}" for key in keys if key in row]
        pieces.append("can_execute_trades=false")
        formatted.append("- " + "; ".join(pieces))
    return formatted


def _format_key_values(values: dict[str, Any]) -> list[str]:
    return [f"- {key}: {value}" for key, value in sorted(values.items())]
