"""Read-only local Streamlit dashboard for TRAIDR."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.components import (  # noqa: E402
    inject_command_center_styles,
    render_command_center_header,
    render_command_center,
    render_database_summary,
    render_daily_mission,
    render_command_strip,
    render_safety_status,
    render_sidebar_status,
    render_setup_instructions,
)
from dashboard import bitunix_cockpit  # noqa: E402
from dashboard.pages import alerts, market_radar, portfolio, reports, token_detail, watchlist  # noqa: E402
from dashboard.queries import configured_database_path, load_dashboard_data  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="TRAIDR Command Center", layout="wide")
    inject_command_center_styles()

    default_database = configured_database_path()
    st.sidebar.markdown(" ")
    database_input = st.sidebar.text_input("DuckDB path", value=str(default_database))
    row_limit = st.sidebar.slider("Rows per section", min_value=5, max_value=100, value=20, step=5)

    data = load_dashboard_data(database_input, limit=row_limit)
    render_sidebar_status(data)
    render_command_center_header(data)

    tabs = st.tabs(
        [
            "Cockpit",
            "Operations",
            "Radar",
            "Token Detail",
            "Watchlist",
            "Portfolio",
            "Alerts",
            "Reports",
            "Safety Status",
        ]
    )
    with tabs[0]:
        bitunix_cockpit.render(database_input)
        lower_left, lower_right = st.columns([1, 2], gap="medium")
        with lower_left:
            render_daily_mission(data)
        with lower_right:
            render_command_strip(database_input, key_prefix="cockpit")
    with tabs[1]:
        render_daily_mission(data)
        render_safety_status(data)
        render_database_summary(data)
        render_command_center(database_input, key_prefix="operations")
        if not data.database_exists:
            render_setup_instructions(str(data.database_path))
    with tabs[2]:
        market_radar.render(data)
    with tabs[3]:
        token_detail.render(data)
    with tabs[4]:
        watchlist.render(data)
    with tabs[5]:
        portfolio.render(data)
    with tabs[6]:
        alerts.render(data)
    with tabs[7]:
        reports.render(data)
    with tabs[8]:
        render_safety_status(data)


if __name__ == "__main__":
    main()
