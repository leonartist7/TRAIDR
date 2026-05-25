"""Build daily local intelligence briefings from DuckDB."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import duckdb

from reports.report_models import BriefingState, DailyBriefing
from storage.schema import list_tables

_NEXT_COMMANDS = (
    "python -m cli.main scan --fixture --database storage/duckdb/traidr.duckdb",
    "python -m cli.main scheduler-once --database storage/duckdb/traidr.duckdb",
    "python scripts/run_simulation.py --database storage/duckdb/traidr.duckdb",
)


def build_daily_briefing(
    connection: duckdb.DuckDBPyConnection,
    *,
    now: datetime | None = None,
    limit: int = 5,
) -> DailyBriefing:
    generated_at = now or datetime.now(timezone.utc)
    tables = list_tables(connection)
    market_summary = _market_scan_summary(connection, tables)
    top_radar = _top_radar_candidates(connection, tables, limit)
    high_risk = _highest_risk_candidates(connection, tables, limit)
    alerts = _new_alerts(connection, tables, limit)
    simulations = _recent_simulation_results(connection, tables, limit)
    missing = _missing_warnings(market_summary, top_radar, alerts, simulations)
    state = _classify_state(market_summary, top_radar, high_risk, alerts, missing)
    reason_codes = _reason_codes(state, missing, top_radar, high_risk, alerts)
    return DailyBriefing(
        state=state,
        generated_at=generated_at,
        market_scan_summary=market_summary,
        top_radar_candidates=top_radar,
        highest_risk_candidates=high_risk,
        new_alerts=alerts,
        recent_simulation_results=simulations,
        current_safety_status=_safety_status(),
        missing_data_warnings=missing,
        suggested_watchlist=_suggested_watchlist(top_radar, market_summary),
        next_commands=_NEXT_COMMANDS if state is BriefingState.INSUFFICIENT_DATA else (),
        reason_codes=reason_codes,
    )


def empty_daily_briefing(
    *,
    now: datetime | None = None,
    reason_codes: tuple[str, ...] = ("BRIEFING_DATABASE_MISSING",),
) -> DailyBriefing:
    generated_at = now or datetime.now(timezone.utc)
    return DailyBriefing(
        state=BriefingState.INSUFFICIENT_DATA,
        generated_at=generated_at,
        market_scan_summary=_empty_market_summary(),
        top_radar_candidates=(),
        highest_risk_candidates=(),
        new_alerts=(),
        recent_simulation_results=(),
        current_safety_status=_safety_status(),
        missing_data_warnings=(
            "NO_MARKET_SCAN_DATA",
            "NO_RADAR_DATA",
            "NO_ALERT_DATA",
            "NO_SIMULATION_DATA",
        ),
        suggested_watchlist=(),
        next_commands=_NEXT_COMMANDS,
        reason_codes=reason_codes,
    )


def _market_scan_summary(connection: duckdb.DuckDBPyConnection, tables: set[str]) -> dict[str, Any]:
    if "evidence_snapshots" not in tables:
        return _empty_market_summary()
    row = connection.execute(
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN quality_status = 'sufficient' THEN 1 ELSE 0 END),
            SUM(CASE WHEN quality_status != 'sufficient' THEN 1 ELSE 0 END),
            MAX(observed_at)
        FROM evidence_snapshots
        WHERE source_name LIKE 'market_scan:%'
        """
    ).fetchone()
    pair_rows = connection.execute(
        """
        SELECT payload_json
        FROM evidence_snapshots
        WHERE source_name LIKE 'market_scan:%'
        ORDER BY collected_at DESC
        LIMIT 10
        """
    ).fetchall()
    pair_ids = tuple(
        pair_id
        for pair_id in (_pair_from_payload(payload_json) for (payload_json,) in pair_rows)
        if pair_id
    )
    count = int(row[0] or 0)
    if count == 0:
        return _empty_market_summary()
    return {
        "total_candidates": count,
        "sufficient_candidates": int(row[1] or 0),
        "insufficient_candidates": int(row[2] or 0),
        "latest_observed_at": row[3].isoformat() if row[3] else None,
        "candidate_pair_ids": list(dict.fromkeys(pair_ids)),
        "can_execute_trades": False,
    }


def _top_radar_candidates(
    connection: duckdb.DuckDBPyConnection,
    tables: set[str],
    limit: int,
) -> tuple[dict[str, Any], ...]:
    if "opportunity_radar_states" not in tables:
        return ()
    rows = connection.execute(
        """
        SELECT subject_id, state, rank, opportunity_score, risk_score, confidence, reason_codes_json
        FROM opportunity_radar_states
        ORDER BY rank ASC, opportunity_score DESC, recorded_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    return tuple(_radar_row(row) for row in rows)


def _highest_risk_candidates(
    connection: duckdb.DuckDBPyConnection,
    tables: set[str],
    limit: int,
) -> tuple[dict[str, Any], ...]:
    if "opportunity_radar_states" not in tables:
        return ()
    rows = connection.execute(
        """
        SELECT subject_id, state, rank, opportunity_score, risk_score, confidence, reason_codes_json
        FROM opportunity_radar_states
        ORDER BY risk_score DESC, recorded_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    return tuple(_radar_row(row) for row in rows)


def _new_alerts(
    connection: duckdb.DuckDBPyConnection,
    tables: set[str],
    limit: int,
) -> tuple[dict[str, Any], ...]:
    if "notification_alerts" not in tables:
        return ()
    rows = connection.execute(
        """
        SELECT recorded_at, subject_id, channel, severity, status, reason_codes_json
        FROM notification_alerts
        ORDER BY recorded_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    return tuple(
        {
            "recorded_at": row[0].isoformat() if row[0] else None,
            "subject_id": row[1],
            "channel": row[2],
            "severity": row[3],
            "status": row[4],
            "reason_codes": _json_list(row[5]),
            "can_execute_trades": False,
        }
        for row in rows
    )


def _recent_simulation_results(
    connection: duckdb.DuckDBPyConnection,
    tables: set[str],
    limit: int,
) -> tuple[dict[str, Any], ...]:
    if "simulated_orders" not in tables:
        return ()
    rows = connection.execute(
        """
        SELECT
            order_id,
            created_at,
            side,
            pair_id,
            notional_usd,
            order_status,
            metadata_json
        FROM simulated_orders
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    fill_counts = _fill_counts(connection, tables)
    return tuple(
        {
            "order_id": row[0],
            "created_at": row[1].isoformat() if row[1] else None,
            "side": row[2],
            "pair_id": row[3],
            "notional_usd": str(row[4]),
            "order_status": row[5],
            "fill_count": fill_counts.get(row[0], 0),
            "metadata": _json_object(row[6]),
            "can_execute_trades": False,
        }
        for row in rows
    )


def _fill_counts(connection: duckdb.DuckDBPyConnection, tables: set[str]) -> dict[str, int]:
    if "simulated_fills" not in tables:
        return {}
    rows = connection.execute(
        """
        SELECT order_id, COUNT(*)
        FROM simulated_fills
        GROUP BY order_id
        """
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def _classify_state(
    market_summary: dict[str, Any],
    top_radar: tuple[dict[str, Any], ...],
    high_risk: tuple[dict[str, Any], ...],
    alerts: tuple[dict[str, Any], ...],
    missing: tuple[str, ...],
) -> BriefingState:
    if market_summary["total_candidates"] == 0 and not top_radar and not alerts:
        return BriefingState.INSUFFICIENT_DATA
    if any(float(row["risk_score"]) >= 70 for row in high_risk):
        return BriefingState.RISK_OFF
    if any(row["severity"] == "CRITICAL" for row in alerts):
        return BriefingState.RISK_OFF
    if "NO_MARKET_SCAN_DATA" in missing or "NO_RADAR_DATA" in missing:
        return BriefingState.INSUFFICIENT_DATA
    if any(row["state"] == "BUY_CANDIDATE" and float(row["confidence"]) >= 0.5 for row in top_radar):
        return BriefingState.RISK_ON
    return BriefingState.NEUTRAL


def _missing_warnings(
    market_summary: dict[str, Any],
    top_radar: tuple[dict[str, Any], ...],
    alerts: tuple[dict[str, Any], ...],
    simulations: tuple[dict[str, Any], ...],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if market_summary["total_candidates"] == 0:
        warnings.append("NO_MARKET_SCAN_DATA")
    if not top_radar:
        warnings.append("NO_RADAR_DATA")
    if not alerts:
        warnings.append("NO_ALERT_DATA")
    if not simulations:
        warnings.append("NO_SIMULATION_DATA")
    if market_summary["insufficient_candidates"]:
        warnings.append("MARKET_SCAN_HAS_INSUFFICIENT_CANDIDATES")
    return tuple(warnings)


def _suggested_watchlist(
    top_radar: tuple[dict[str, Any], ...],
    market_summary: dict[str, Any],
) -> tuple[str, ...]:
    radar_subjects = [
        str(row["subject_id"])
        for row in top_radar
        if row["state"] in {"BUY_CANDIDATE", "ALERT", "WATCH"}
    ]
    if radar_subjects:
        return tuple(dict.fromkeys(radar_subjects))[:5]
    return tuple(market_summary.get("candidate_pair_ids", ()))[:5]


def _reason_codes(
    state: BriefingState,
    missing: tuple[str, ...],
    top_radar: tuple[dict[str, Any], ...],
    high_risk: tuple[dict[str, Any], ...],
    alerts: tuple[dict[str, Any], ...],
) -> tuple[str, ...]:
    reasons = ["BRIEFING_READ_ONLY", f"BRIEFING_{state.value}"]
    reasons.extend(missing)
    if top_radar:
        reasons.append("RADAR_DATA_AVAILABLE")
    if high_risk:
        reasons.append("RISK_DATA_AVAILABLE")
    if alerts:
        reasons.append("ALERT_DATA_AVAILABLE")
    return tuple(dict.fromkeys(reasons))


def _safety_status() -> dict[str, Any]:
    return {
        "simulation_only": True,
        "live_trading": False,
        "withdrawals": False,
        "private_key_handling": False,
        "ai_direct_execution": False,
        "no_execution_actions": True,
        "can_execute_trades": False,
    }


def _empty_market_summary() -> dict[str, Any]:
    return {
        "total_candidates": 0,
        "sufficient_candidates": 0,
        "insufficient_candidates": 0,
        "latest_observed_at": None,
        "candidate_pair_ids": [],
        "can_execute_trades": False,
    }


def _radar_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "subject_id": row[0],
        "state": row[1],
        "rank": int(row[2]),
        "opportunity_score": float(row[3]),
        "risk_score": float(row[4]),
        "confidence": float(row[5]),
        "reason_codes": _json_list(row[6]),
        "can_execute_trades": False,
    }


def _pair_from_payload(payload_json: str) -> str | None:
    payload = _json_object(payload_json)
    pair_id = payload.get("pair_id") or payload.get("token_pair_id")
    return str(pair_id) if pair_id else None


def _json_list(value: str) -> list[Any]:
    parsed = _json_value(value, [])
    return parsed if isinstance(parsed, list) else []


def _json_object(value: str) -> dict[str, Any]:
    parsed = _json_value(value, {})
    return parsed if isinstance(parsed, dict) else {}


def _json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback
