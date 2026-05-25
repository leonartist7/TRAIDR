"""Market radar and scan evidence dashboard page."""

from __future__ import annotations

import streamlit as st

from dashboard.components import render_risk_first_tables, render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("Market Radar")
    st.caption("Research-only radar. Risk evidence is shown before opportunities.")
    risk_rows = sorted(data.market_radar, key=lambda row: float(row.get("risk_score") or 0), reverse=True)
    opportunity_rows = sorted(data.market_radar, key=lambda row: float(row.get("opportunity_score") or 0), reverse=True)
    render_risk_first_tables("Highest Risks", risk_rows, "Best Opportunities", opportunity_rows)

    st.header("Scan Evidence")
    render_table("Latest Scan Evidence", data.scan_evidence)
