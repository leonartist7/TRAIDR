"""Manual portfolio dashboard page."""

from __future__ import annotations

import streamlit as st

from dashboard.components import render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("Portfolio")
    st.caption("Local paper accounting only. TRAIDR does not connect to exchanges or wallets.")
    render_table("Paper Futures Portfolio", data.paper_futures_portfolios)
    render_table("Paper Futures Positions", data.paper_futures_positions)
    render_table("Paper Orders", data.paper_futures_orders)
    render_table("Paper Fills", data.paper_futures_fills)
    render_table("Funding Ledger", data.paper_funding_events)
    render_table("Order State Audit", data.paper_order_events)
    render_table("Correlation / Simultaneous-Loss Stress", data.paper_stress_snapshots)
    render_table("Manual Positions", data.portfolio_entries)
    render_table("Risk Decisions", data.risk_decisions)
    render_table("Simulated Orders", data.simulated_orders)
    render_table("Simulated Fills", data.simulated_fills)
