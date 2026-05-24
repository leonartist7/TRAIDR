"""Reusable read-only Streamlit dashboard components."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

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


def render_table(title: str, rows: Sequence[Mapping[str, Any]]) -> None:
    """Render a read-only table section with empty-state handling."""

    st.subheader(title)
    if not rows:
        st.caption("No rows found.")
        return
    st.dataframe([dict(row) for row in rows], use_container_width=True, hide_index=True)


def _yes_no(value: Any) -> str:
    return "yes" if value is True else "no"
