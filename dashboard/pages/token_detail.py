"""Token detail dashboard page."""

from __future__ import annotations

import streamlit as st

from dashboard.components import render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("Token Detail")
    st.caption("Local token evidence only. No execution controls are available.")
    render_table("Token Evidence", data.token_details)
    render_table("Technical Vectors", data.technical_vectors)
    render_table("Anti-Rug Status", data.anti_rug_status)
