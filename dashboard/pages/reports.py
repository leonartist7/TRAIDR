"""Reports dashboard page."""

from __future__ import annotations

import streamlit as st

from dashboard.components import render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("Reports")
    st.caption("Research summaries are local and non-executing.")
    render_table("Research Reports", data.reports)
    render_table("Audit Events", data.audit_events)
