"""Watchlist dashboard page."""

from __future__ import annotations

import streamlit as st

from dashboard.components import render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("Watchlist")
    st.caption("Local watchlist entries are read-only from the dashboard.")
    render_table("Watched Pairs", data.watchlist_entries)
