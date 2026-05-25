"""Manual portfolio dashboard page."""

from __future__ import annotations

import streamlit as st

from dashboard.components import render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("Portfolio")
    st.caption("Manual portfolio analysis only. TRAIDR does not connect to exchanges or wallets.")
    render_table("Manual Positions", data.portfolio_entries)
    render_table("Risk Decisions", data.risk_decisions)
    render_table("Simulated Orders", data.simulated_orders)
    render_table("Simulated Fills", data.simulated_fills)
