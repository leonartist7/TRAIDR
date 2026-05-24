"""Read-only local Streamlit dashboard for TRAIDR."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.components import (  # noqa: E402
    render_database_summary,
    render_safety_status,
    render_setup_instructions,
    render_table,
)
from dashboard.queries import configured_database_path, load_dashboard_data  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="TRAIDR Dashboard", layout="wide")
    st.title("TRAIDR Local Dashboard")
    st.caption("Read-only simulation research view. No trading or order execution controls exist here.")

    default_database = configured_database_path()
    database_input = st.sidebar.text_input("DuckDB path", value=str(default_database))
    row_limit = st.sidebar.slider("Rows per section", min_value=5, max_value=100, value=20, step=5)
    st.sidebar.warning("Read-only dashboard. No live trading. No withdrawals. No secret input.")

    data = load_dashboard_data(database_input, limit=row_limit)
    render_safety_status(data)
    render_database_summary(data)

    if not data.database_exists:
        render_setup_instructions(str(data.database_path))
        return

    render_table("Latest Market Snapshots", data.market_snapshots)
    render_table("Technical Vectors", data.technical_vectors)
    render_table("Anti-Rug Status", data.anti_rug_status)
    render_table("Risk Decisions", data.risk_decisions)
    render_table("Simulated Orders", data.simulated_orders)
    render_table("Simulated Fills", data.simulated_fills)
    render_table("Audit Events", data.audit_events)


if __name__ == "__main__":
    main()
