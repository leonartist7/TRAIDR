"""Monitor manual portfolio entries against local research evidence."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

import duckdb

from portfolio.models import ManualPortfolioEntry
from portfolio.repository import PortfolioRepository
from portfolio.sell_risk import PositionEvidence, SellRiskDecision, evaluate_sell_risk
from storage.schema import list_tables


def monitor_positions(
    connection: duckdb.DuckDBPyConnection,
    *,
    now: datetime | None = None,
) -> tuple[SellRiskDecision, ...]:
    entries = PortfolioRepository(connection).list_entries(active_only=True)
    return tuple(
        evaluate_sell_risk(entry, load_position_evidence(connection, entry), now=now)
        for entry in entries
    )


def load_position_evidence(
    connection: duckdb.DuckDBPyConnection,
    entry: ManualPortfolioEntry,
) -> PositionEvidence:
    tables = list_tables(connection)
    current_scan, previous_scan = _latest_scan_payloads(connection, tables, entry)
    current_radar, previous_radar = _latest_radar_rows(connection, tables, entry)
    macro_news = _latest_macro_news(connection, tables)
    return PositionEvidence(
        current_price_usd=_decimal_or_none(current_scan.get("price_usd") if current_scan else None),
        current_liquidity_usd=_decimal_or_none(current_scan.get("liquidity_usd") if current_scan else None),
        previous_liquidity_usd=_decimal_or_none(previous_scan.get("liquidity_usd") if previous_scan else None),
        risk_score=_float_or_none(current_radar.get("risk_score") if current_radar else None),
        previous_risk_score=_float_or_none(previous_radar.get("risk_score") if previous_radar else None),
        radar_state=str(current_radar.get("state")) if current_radar and current_radar.get("state") else None,
        previous_radar_state=str(previous_radar.get("state")) if previous_radar and previous_radar.get("state") else None,
        opportunity_score=_float_or_none(current_radar.get("opportunity_score") if current_radar else None),
        previous_opportunity_score=_float_or_none(previous_radar.get("opportunity_score") if previous_radar else None),
        token_safety_complete=_token_safety_complete(current_radar),
        macro_news_classification=macro_news,
    )


def _latest_scan_payloads(
    connection: duckdb.DuckDBPyConnection,
    tables: set[str],
    entry: ManualPortfolioEntry,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if "evidence_snapshots" not in tables:
        return {}, {}
    rows = connection.execute(
        """
        SELECT payload_json
        FROM evidence_snapshots
        WHERE source_name LIKE 'market_scan:%'
        ORDER BY collected_at DESC
        LIMIT 25
        """
    ).fetchall()
    matches = [
        payload
        for payload in (_json_object(row[0]) for row in rows)
        if _matches_entry(payload, entry)
    ]
    current = matches[0] if matches else {}
    previous = matches[1] if len(matches) > 1 else {}
    return current, previous


def _latest_radar_rows(
    connection: duckdb.DuckDBPyConnection,
    tables: set[str],
    entry: ManualPortfolioEntry,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if "opportunity_radar_states" not in tables:
        return {}, {}
    subjects = _subject_candidates(entry)
    rows = connection.execute(
        """
        SELECT subject_id, state, opportunity_score, risk_score, reason_codes_json
        FROM opportunity_radar_states
        WHERE subject_id IN (?, ?, ?)
        ORDER BY recorded_at DESC
        LIMIT 2
        """,
        list(subjects),
    ).fetchall()
    mapped = [
        {
            "subject_id": row[0],
            "state": row[1],
            "opportunity_score": row[2],
            "risk_score": row[3],
            "reason_codes": _json_list(row[4]),
        }
        for row in rows
    ]
    current = mapped[0] if mapped else {}
    previous = mapped[1] if len(mapped) > 1 else {}
    return current, previous


def _latest_macro_news(connection: duckdb.DuckDBPyConnection, tables: set[str]) -> str | None:
    if "macro_news_events" not in tables:
        return None
    row = connection.execute(
        """
        SELECT classification
        FROM macro_news_events
        ORDER BY recorded_at DESC
        LIMIT 1
        """
    ).fetchone()
    return str(row[0]) if row else None


def _matches_entry(payload: dict[str, Any], entry: ManualPortfolioEntry) -> bool:
    pair_id = str(payload.get("pair_id") or payload.get("token_pair_id") or "")
    return pair_id in _subject_candidates(entry)


def _subject_candidates(entry: ManualPortfolioEntry) -> tuple[str, str, str]:
    return (entry.pair_ref, entry.pair_ref.split("/", 1)[-1], entry.symbol)


def _token_safety_complete(radar: dict[str, Any]) -> bool | None:
    if not radar:
        return None
    reasons = set(str(reason) for reason in radar.get("reason_codes") or ())
    if "TOKEN_SAFETY_UNKNOWN" in reasons or "TOKEN_SAFETY_HARD_FAIL" in reasons:
        return False
    return True


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []
