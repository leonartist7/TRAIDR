"""Translate local dashboard rows into safe, typed API read models."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from dashboard.queries import (
    DashboardData,
    load_dashboard_data,
    load_market_candles,
    load_market_instruments,
)
from data_pipeline.provider_contracts import PROVIDER_ACCESS_POLICIES
from web_api.contracts import (
    ApiStatus,
    CandleData,
    FreshnessInfo,
    MarketData,
    MarketInstrumentData,
    MarketsData,
    OverviewData,
    ScannerData,
    ScannerFactorData,
    ScannerRow,
    ShadowEvidenceData,
    StatusData,
)

MAX_API_AGE_SECONDS = 300.0


def read_dashboard(database_path: str | Path, *, limit: int) -> DashboardData:
    """Read the service-owned database through the existing dashboard query layer."""

    return load_dashboard_data(database_path, limit=limit)


def build_status(data: DashboardData) -> StatusData:
    latest_heartbeat = max(
        (
            timestamp
            for row in data.service_heartbeats
            if (timestamp := _as_datetime(row.get("heartbeat_at"))) is not None
        ),
        default=None,
    )
    circuit_health = {
        str(row.get("provider")): row
        for row in data.provider_circuits
    }
    latest_shadow: dict[str, dict[str, Any]] = {}
    for row in data.shadow_evidence:
        latest_shadow.setdefault(str(row.get("provider")), row)
    provider_health = [
        {
            "provider": policy.provider,
            "role": policy.role,
            "auth_mode": policy.auth_mode,
            "cost_tier": policy.cost_tier,
            "quota_model": policy.quota_model,
            "freshness_target_seconds": policy.freshness_target_seconds,
            "licensing": policy.licensing,
            "shadow_only": policy.shadow_only,
            "research_only": policy.research_only,
            "state": circuit_health.get(policy.provider, {}).get(
                "state", "OBSERVED" if policy.provider in latest_shadow else "DATA_NOT_AVAILABLE"
            ),
            "observed_at": latest_shadow.get(policy.provider, {}).get("observed_at"),
            "reason_codes": _json_strings(latest_shadow.get(policy.provider, {}).get("reason_codes_json")),
            "can_execute_trades": False,
        }
        for policy in PROVIDER_ACCESS_POLICIES.values()
    ]
    return StatusData(
        database_exists=data.database_exists,
        table_count=len(data.tables),
        service_state=_service_state(data),
        latest_heartbeat=latest_heartbeat,
        provider_health=provider_health,
        safety=dict(data.safety_status),
    )


def build_scanner(
    data: DashboardData,
    *,
    limit: int,
    status: str | None = None,
    direction: str | None = None,
    instrument_id: str | None = None,
) -> ScannerData:
    shadow_by_instrument = {
        str(row.get("instrument_id")): row
        for row in reversed(data.shadow_evidence)
        if row.get("provider") == "traidr_shadow_strategy"
    }
    rows = [
        _scanner_row(row, shadow_by_instrument.get(str(row.get("instrument_id"))))
        for row in data.scanner_scores
        if (instrument_id is None or row.get("instrument_id") == instrument_id)
        if (status is None or str(row.get("status", "")).upper() == status.upper())
        and (direction is None or str(row.get("direction", "")).upper() == direction.upper())
    ]
    return ScannerData(rows=rows[:limit], limit=limit, total=len(rows))


def build_overview(data: DashboardData, *, limit: int) -> OverviewData:
    scanner = build_scanner(data, limit=limit).rows
    return OverviewData(
        scanner=scanner,
        alerts=[_public_alert(row) for row in data.alerts[:limit]],
        paper_positions=[_public_position(row) for row in data.paper_futures_positions[:limit]],
        service_heartbeats=[_public_heartbeat(row) for row in data.service_heartbeats[:limit]],
        shadow_evidence=[
            _shadow_evidence(row)
            for row in data.shadow_evidence
            if row.get("provider") == "traidr_shadow_strategy"
        ][:limit],
        news=[_public_news(row) for row in data.news_evidence[:limit]],
    )


def build_market(
    data: DashboardData,
    *,
    instrument_id: str,
    interval: str,
    limit: int,
) -> MarketData:
    candles = [
        CandleData(
            open_time_ms=int(row["open_time_ms"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            base_volume=float(row["base_volume"]),
            quote_volume=float(row["quote_volume"]),
            source=str(row["source"]),
            received_at=received_at,
            quality=str(row["quality"]),
        )
        for row in load_market_candles(data.database_path, instrument_id, interval, limit=limit)
        if (received_at := _as_datetime(row.get("received_at"))) is not None
    ]
    scanner = next(
        (
            _scanner_row(
                row,
                next(
                    (
                        item for item in data.shadow_evidence
                        if item.get("instrument_id") == instrument_id
                        and item.get("provider") == "traidr_shadow_strategy"
                    ),
                    None,
                ),
            )
            for row in data.scanner_scores
            if row.get("instrument_id") == instrument_id
        ),
        None,
    )
    microstructure = [
        _public_microstructure(row)
        for row in data.market_microstructure
        if row.get("instrument_id") == instrument_id
    ][:limit]
    evidence = [
        _public_evidence(row)
        for row in data.evidence_bundles
        if row.get("instrument_id") == instrument_id
    ][:limit]
    return MarketData(
        instrument_id=instrument_id,
        interval=interval,
        candles=candles,
        scanner=scanner,
        microstructure=microstructure,
        evidence=evidence,
    )


def build_markets(data: DashboardData, *, limit: int) -> MarketsData:
    instruments = [
        MarketInstrumentData(
            instrument_id=str(row["instrument_id"]),
            source=str(row["source"]),
            symbol=str(row["symbol"]),
            base_asset=str(row["base_asset"]),
            quote_asset=str(row["quote_asset"]),
            status=str(row["status"]),
            discovered_at=discovered_at,
            refreshed_at=refreshed_at,
        )
        for row in load_market_instruments(data.database_path, limit=limit)
        if (discovered_at := _as_datetime(row.get("discovered_at"))) is not None
        and (refreshed_at := _as_datetime(row.get("refreshed_at"))) is not None
    ]
    return MarketsData(instruments=instruments, limit=limit, total=len(instruments))


def status_for(data: DashboardData, *, has_data: bool | None = None) -> ApiStatus:
    if not data.database_exists:
        return "INSUFFICIENT_DATA"
    if _service_state(data) == "DEGRADED":
        return "DEGRADED"
    if has_data is False:
        return "INSUFFICIENT_DATA"
    return "OK"


def reason_codes_for(data: DashboardData, *, has_data: bool | None = None) -> tuple[str, ...]:
    reasons: list[str] = []
    if not data.database_exists:
        reasons.append("DATABASE_NOT_FOUND")
    if _service_state(data) == "DEGRADED":
        reasons.append("LOCAL_SERVICE_DEGRADED")
    if has_data is False:
        reasons.append("NO_DATA_FOR_REQUEST")
    return tuple(dict.fromkeys(reasons))


def freshness_for(
    observed_at: datetime | None,
    *,
    maximum_age_seconds: float = MAX_API_AGE_SECONDS,
    now: datetime | None = None,
) -> FreshnessInfo:
    if observed_at is None:
        return FreshnessInfo(state="UNKNOWN", maximum_age_seconds=maximum_age_seconds)
    reference = _as_datetime(now) or datetime.now(tz=UTC)
    observed = _as_datetime(observed_at)
    if observed is None:
        return FreshnessInfo(state="UNKNOWN", maximum_age_seconds=maximum_age_seconds)
    age = (reference - observed).total_seconds()
    if age < 0:
        return FreshnessInfo(state="UNKNOWN", observed_at=observed, maximum_age_seconds=maximum_age_seconds)
    return FreshnessInfo(
        state="FRESH" if age <= maximum_age_seconds else "STALE",
        observed_at=observed,
        age_seconds=age,
        maximum_age_seconds=maximum_age_seconds,
    )


def latest_observation(data: DashboardData) -> datetime | None:
    timestamps = [
        timestamp
        for row in (*data.scanner_scores, *data.market_microstructure, *data.data_health)
        for timestamp in (_as_datetime(row.get("observed_at")), _as_datetime(row.get("checked_at")))
        if timestamp is not None
    ]
    return max(timestamps, default=None)


def scanner_reason_codes(data: DashboardData, *, has_data: bool) -> tuple[str, ...]:
    if not has_data:
        return (*reason_codes_for(data, has_data=False), "SCANNER_DATA_UNAVAILABLE")
    return tuple(
        dict.fromkeys(
            reason
            for row in data.scanner_scores
            for reason in _json_strings(row.get("reason_codes_json"))
        )
    )


def _scanner_row(row: dict[str, Any], shadow: dict[str, Any] | None = None) -> ScannerRow:
    return ScannerRow(
        score_id=str(row.get("score_id", "")),
        instrument_id=str(row.get("instrument_id", "")),
        observed_at=_as_datetime(row.get("observed_at")),
        recorded_at=_as_datetime(row.get("recorded_at")),
        status=str(row.get("status", "INSUFFICIENT_DATA")),
        direction=str(row.get("direction", "NO_TRADE")),
        score=_as_float(row.get("score")),
        long_score=_as_float(row.get("long_score")),
        short_score=_as_float(row.get("short_score")),
        risk_score=_as_float(row.get("risk_score")),
        conflicts=_json_strings(row.get("conflicts_json")),
        reason_codes=_json_strings(row.get("reason_codes_json")),
        factors=[_scanner_factor(item) for item in _json_objects(row.get("factor_breakdown_json"))],
        shadow=_shadow_evidence(shadow) if shadow is not None else None,
    )


def _shadow_evidence(row: dict[str, Any]) -> ShadowEvidenceData:
    assessment = _json_object(row.get("assessment_json"))
    fields = {
        key: value
        for key, raw in _json_object(row.get("fields_json")).items()
        if (value := _as_float(raw)) is not None
    }
    observed_at = _as_datetime(row.get("observed_at"))
    freshness = freshness_for(observed_at).state
    return ShadowEvidenceData(
        provider=str(row.get("provider", "unknown")),
        observed_at=observed_at,
        freshness=freshness,
        setup_class=str(assessment.get("setup_class", "INSUFFICIENT_DATA")),
        market_regime=str(assessment.get("market_regime", "INSUFFICIENT_DATA")),
        crowding_score=_as_float(assessment.get("crowding_score")),
        squeeze_risk=_as_float(assessment.get("squeeze_risk")),
        catalyst_risk=_as_float(assessment.get("catalyst_risk")),
        data_quality_score=_as_float(assessment.get("data_quality_score")) or 0.0,
        probability_state=str(assessment.get("probability_state", "UNCALIBRATED")),
        fields=fields,
        conflicts=_json_strings(assessment.get("conflicts")),
        reason_codes=_json_strings(row.get("reason_codes_json")),
    )


def _scanner_factor(value: dict[str, Any]) -> ScannerFactorData:
    return ScannerFactorData(
        factor=str(value.get("factor", "unknown")),
        weight=_as_float(value.get("weight")) or 0.0,
        raw_value=_as_float(value.get("raw_value")),
        normalized_value=_as_float(value.get("normalized_value")),
        long_contribution=_as_float(value.get("long_contribution")) or 0.0,
        short_contribution=_as_float(value.get("short_contribution")) or 0.0,
        explanation=str(value.get("explanation", "")),
        source=str(value["source"]) if value.get("source") is not None else None,
        reason_codes=_json_strings(value.get("reason_codes")),
    )


def _service_state(data: DashboardData) -> str:
    if not data.database_exists:
        return "INSUFFICIENT_DATA"
    statuses = {
        str(row.get("status", "")).upper()
        for row in (*data.data_health, *data.service_heartbeats, *data.provider_circuits)
    }
    if statuses & {"DOWN", "STALE", "DEGRADED", "OPEN"}:
        return "DEGRADED"
    if data.service_heartbeats and statuses & {"RUNNING", "HEALTHY", "OK"}:
        return "RUNNING"
    return "UNKNOWN"


def _public_alert(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "alert_id": row.get("alert_id"),
        "recorded_at": row.get("recorded_at"),
        "subject_id": row.get("subject_id"),
        "channel": row.get("channel"),
        "severity": row.get("severity"),
        "status": row.get("status"),
        "reason_codes": _json_strings(row.get("reason_codes_json")),
        "can_execute_trades": False,
    }


def _public_position(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "position_id": row.get("position_id"),
        "instrument_id": row.get("instrument_id"),
        "direction": row.get("direction"),
        "opened_at": row.get("opened_at"),
        "updated_at": row.get("updated_at"),
        "status": row.get("status"),
        "can_execute_trades": False,
    }


def _public_heartbeat(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "service_name": row.get("service_name"),
        "heartbeat_at": row.get("heartbeat_at"),
        "status": row.get("status"),
        "data_mode": row.get("data_mode"),
        "can_execute_trades": False,
    }


def _public_news(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": row.get("evidence_id"),
        "canonical_asset_id": row.get("canonical_asset_id"),
        "source": row.get("source"),
        "headline": row.get("headline"),
        "url": row.get("url"),
        "published_at": row.get("published_at"),
        "reliability": row.get("reliability"),
        "relevance": row.get("relevance"),
        "mapping_state": row.get("mapping_state"),
        "reason_codes": _json_strings(row.get("reason_codes_json")),
        "evidence_kind": "OBSERVED_FACT",
        "directional_authority": "NONE",
        "can_execute_trades": False,
    }


def _public_microstructure(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "metric_id",
            "instrument_id",
            "observed_at",
            "bid_price",
            "ask_price",
            "spread_bps",
            "depth_imbalance",
            "trade_delta",
            "basis_bps",
            "funding_rate",
        )
    } | {"can_execute_trades": False}


def _public_evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "bundle_id",
            "instrument_id",
            "canonical_asset_id",
            "observed_at",
            "data_coverage",
            "hard_vetoes_json",
            "reason_codes_json",
        )
    } | {"can_execute_trades": False}


def _json_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, str):
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [item for item in decoded if isinstance(item, dict)] if isinstance(decoded, list) else []


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _json_strings(value: Any) -> list[str]:
    if isinstance(value, (tuple, list)):
        return [str(item) for item in value]
    if not isinstance(value, str):
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in decoded] if isinstance(decoded, list) else []


def _as_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
