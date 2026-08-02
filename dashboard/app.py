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
    render_database_summary,
    render_daily_mission,
    render_safety_status,
    render_sidebar_status,
)
from dashboard import bitunix_cockpit  # noqa: E402
from dashboard.pages import alerts, live_scanner, market_radar, portfolio, reports, system_health, token_detail, watchlist  # noqa: E402
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
            "Live Scanner",
            "Operations",
            "Radar",
            "Token Detail",
            "Watchlist",
            "Portfolio",
            "Alerts",
            "Reports",
            "Safety Status",
            "System Health",
        ]
    )
    with tabs[0]:
        bitunix_cockpit.render(database_input)
        lower_left, lower_right = st.columns([1, 2], gap="medium")
        with lower_left:
            render_daily_mission(data)
        with lower_right:
            st.info(
                "The cockpit is read-only. Use System Health for the loopback-only "
                "refresh and paper-simulation controls."
            )
    with tabs[1]:
        live_scanner.render(data)
    with tabs[2]:
        render_daily_mission(data)
        render_safety_status(data)
        render_database_summary(data)
        if not data.database_exists:
            st.info(
                "Start the single-writer service with `python -m cli.main service run` "
                "to initialize validated live research data."
            )
        else:
            st.info(
                "All production state changes go through the single-writer service. "
                "Direct dashboard database actions are disabled."
            )
    with tabs[3]:
        market_radar.render(data)
    with tabs[4]:
        token_detail.render(data)
    with tabs[5]:
        watchlist.render(data)
    with tabs[6]:
        portfolio.render(data)
    with tabs[7]:
        alerts.render(data)
    with tabs[8]:
        reports.render(data)
    with tabs[9]:
        render_safety_status(data)
    with tabs[10]:
        system_health.render(data)


if __name__ == "__main__":
    main()
