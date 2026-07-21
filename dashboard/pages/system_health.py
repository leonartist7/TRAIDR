"""Always-on service, source freshness, and calibration health page."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib import error, request
from uuid import uuid4

import streamlit as st

from dashboard.components import render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("System Health")
    st.caption(
        "Public-source lag, reconnects, gaps, coverage, and model eligibility. "
        "These local controls cannot place exchange orders."
    )
    heartbeat = data.service_heartbeats[0] if data.service_heartbeats else None
    columns = st.columns(4)
    if heartbeat:
        heartbeat_at = heartbeat.get("heartbeat_at")
        age = None
        if hasattr(heartbeat_at, "tzinfo"):
            aware = heartbeat_at.replace(tzinfo=UTC) if heartbeat_at.tzinfo is None else heartbeat_at
            age = max(0, int((datetime.now(tz=UTC) - aware).total_seconds()))
        columns[0].metric("Service", heartbeat.get("status", "UNKNOWN"))
        columns[1].metric("Heartbeat Age", f"{age}s" if age is not None else "unknown")
        columns[2].metric("Data Mode", heartbeat.get("data_mode", "unknown"))
    else:
        columns[0].metric("Service", "OFFLINE")
        columns[1].metric("Heartbeat Age", "missing")
        columns[2].metric("Data Mode", "unknown")
    columns[3].metric("Can Execute Trades", "false")

    control_columns = st.columns(3)
    if control_columns[0].button("Refresh Research Service", use_container_width=True):
        _show_control_result("refresh")
    if control_columns[1].button(
        "Enable Auto Paper Simulation",
        use_container_width=True,
        help="Allows only risk-approved local paper positions. It never sends an exchange order.",
    ):
        _show_control_result("paper_enable")
    if control_columns[2].button("Disable Auto Paper Simulation", use_container_width=True):
        _show_control_result("paper_disable")

    render_table("Source / Channel Health", data.data_health)
    render_table("Ingestion Gaps and Recovery", data.ingestion_gaps)
    render_table("Provider Circuit Breakers", data.provider_circuits)
    render_table("Probability Calibration", data.calibration_reports)
    render_table("Model Champion / Challenger Artifacts", data.model_artifacts)
    render_table("Production Certification", data.certification_runs)


def _show_control_result(action: str) -> None:
    try:
        result = _send_control(action)
    except (OSError, ValueError) as exc:
        st.error(f"Local service control is unavailable: {exc}")
        return
    st.success(f"Request accepted: {result.get('status', 'ACCEPTED')}")


def _send_control(action: str) -> dict[str, object]:
    payload = json.dumps({"idempotency_key": str(uuid4())}).encode("utf-8")
    control_request = request.Request(
        f"http://127.0.0.1:8765/{action}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-TRAIDR-Control": "local-dashboard",
        },
        method="POST",
    )
    try:
        with request.urlopen(control_request, timeout=2) as response:  # noqa: S310 - fixed loopback URL
            decoded = json.loads(response.read())
    except error.HTTPError as exc:
        raise ValueError(f"service rejected the request ({exc.code})") from exc
    except error.URLError as exc:
        raise OSError("start `traidr service run` first") from exc
    if not isinstance(decoded, dict):
        raise ValueError("service returned an invalid response")
    return decoded
