"""Reusable read-only Streamlit dashboard components."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

from dashboard.actions import run_dashboard_action
from dashboard.queries import DashboardData


def render_setup_instructions(database_path: str) -> None:
    """Show friendly setup instructions when the local database is absent."""

    st.info("No local TRAIDR DuckDB database was found yet.")
    st.code(
        f"python scripts/run_simulation.py --database {database_path}\n"
        "python -m streamlit run dashboard/app.py",
        language="bash",
    )


def render_safety_status(data: DashboardData) -> None:
    """Render static safety posture from local config."""

    st.subheader("Safety Status")
    safety = data.safety_status
    columns = st.columns(4)
    columns[0].metric("Mode", str(safety.get("runtime_mode")))
    columns[1].metric("Live Trading", _yes_no(safety.get("live_trading_implemented")))
    columns[2].metric("Withdrawals", _yes_no(safety.get("withdrawals_implemented")))
    columns[3].metric("LLM Execution", _yes_no(safety.get("llm_direct_order_execution_allowed")))
    render_table(
        "Safety Config",
        [
            {"setting": key, "value": value}
            for key, value in sorted(safety.items())
        ],
    )


def render_database_summary(data: DashboardData) -> None:
    """Render a compact local database summary."""

    st.subheader("Local Database")
    st.write(f"Path: `{data.database_path}`")
    st.write(f"Tables: {', '.join(sorted(data.tables)) if data.tables else 'none'}")


def render_command_center(database_path: str) -> None:
    """Render safe local action buttons for daily operator workflows."""

    st.subheader("Command Center")
    st.caption("Buttons run local TRAIDR research workflows. They cannot live trade, withdraw, or access secrets.")

    actions = (
        ("Run Daily Workflow", "daily_run", "Scan fixtures, update radar, generate alerts, and save a report."),
        ("Run Fixture Scan", "fixture_scan", "Create offline scan evidence and radar candidates."),
        ("Run Paper Simulation", "paper_simulation", "Record a risk-gated paper-only simulation."),
        ("Show Briefing", "briefing", "Generate a local daily briefing from DuckDB."),
        ("Show Alerts", "alerts", "Read local alert history."),
        ("Generate Test Alerts", "alerts_test", "Create deterministic local alert examples."),
        ("Run Scheduler Once", "scheduler_once", "Run due research scheduler tasks one time."),
        ("Refresh Fixture Radar", "fixture_radar", "Display fixture radar output."),
        ("Check Status", "status", "Show safety and database status."),
    )

    columns = st.columns(3)
    for index, (label, action, help_text) in enumerate(actions):
        if columns[index % 3].button(label, key=f"dashboard_action_{action}", help=help_text, width="stretch"):
            with st.spinner(f"Running {label}..."):
                result = run_dashboard_action(action, database=database_path)
            if result.exit_code == 0:
                st.success(f"{result.label} completed. can_execute_trades: {result.can_execute_trades}")
            else:
                st.error(f"{result.label} failed safely. can_execute_trades: {result.can_execute_trades}")
            st.code(result.output, language="text")
            st.info("Use the app refresh control or rerun the page to reload the tables below.")


def render_risk_first_tables(
    risk_title: str,
    risk_rows: Sequence[Mapping[str, Any]],
    opportunity_title: str,
    opportunity_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Render risk evidence before opportunity evidence."""

    render_table(risk_title, risk_rows)
    render_table(opportunity_title, opportunity_rows)


def render_table(title: str, rows: Sequence[Mapping[str, Any]]) -> None:
    """Render a read-only table section with empty-state handling."""

    st.subheader(title)
    if not rows:
        st.caption("No rows found.")
        return
    st.dataframe([_display_row(row) for row in rows], width="stretch", hide_index=True)


def _yes_no(value: Any) -> str:
    return "yes" if value is True else "no"


def _display_row(row: Mapping[str, Any]) -> dict[str, Any]:
    display: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list, tuple, set)):
            display[key] = str(value)
        elif isinstance(value, bool):
            display[key] = "false" if value is False else "true"
        elif value is None:
            display[key] = ""
        else:
            display[key] = value
    return display
