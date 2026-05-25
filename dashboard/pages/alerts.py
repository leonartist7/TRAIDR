"""Alerts dashboard page."""

from __future__ import annotations

import streamlit as st

from dashboard.components import render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("Alerts")
    st.caption("Local notification history only. Alerts cannot execute trades.")
    render_table("Latest Alerts", data.alerts)
