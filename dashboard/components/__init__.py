"""Reusable read-only Streamlit dashboard components."""

from __future__ import annotations

from html import escape
from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

from dashboard.actions import run_dashboard_action
from dashboard.queries import DashboardData
from dashboard.view_models import (
    CommandCard,
    build_command_cards,
    build_daily_mission,
    build_dashboard_health,
    summarize_action_output,
)


def inject_command_center_styles() -> None:
    """Install the TRAIDR command-center visual system."""

    st.markdown(
        """
        <style>
        :root {
          --traidr-bg: #070a0f;
          --traidr-panel: #0d131b;
          --traidr-panel-2: #111923;
          --traidr-border: #263241;
          --traidr-text: #f4f7fb;
          --traidr-muted: #9da8b7;
          --traidr-cyan: #20d9ff;
          --traidr-green: #53e06b;
          --traidr-red: #ff4d55;
          --traidr-blue: #6aa7ff;
        }
        .stApp {
          background:
            radial-gradient(circle at 18% 0%, rgba(32, 217, 255, 0.10), transparent 28rem),
            linear-gradient(180deg, #070a0f 0%, #080b10 42%, #05070b 100%);
          color: var(--traidr-text);
        }
        [data-testid="stSidebarNav"] { display: none; }
        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #111521 0%, #0a0e14 100%);
          border-right: 1px solid rgba(148, 163, 184, 0.18);
        }
        h1, h2, h3 { letter-spacing: 0; }
        div[data-testid="stMetric"] {
          background: linear-gradient(180deg, rgba(17, 25, 35, 0.96), rgba(10, 15, 22, 0.96));
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 8px;
          padding: 0.7rem 0.8rem;
        }
        div[data-testid="stMetric"] label {
          color: var(--traidr-muted);
        }
        .traidr-shell-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          padding: 0.25rem 0 1rem 0;
          border-bottom: 1px solid rgba(148, 163, 184, 0.16);
          margin-bottom: 1rem;
        }
        .traidr-title h1 {
          margin: 0;
          font-size: clamp(2rem, 3vw, 3rem);
          line-height: 1;
          font-weight: 800;
        }
        .traidr-title p {
          margin: 0.55rem 0 0;
          color: var(--traidr-muted);
          font-size: 0.98rem;
        }
        .traidr-status-row {
          display: flex;
          flex-wrap: wrap;
          justify-content: flex-end;
          gap: 0.5rem;
        }
        .traidr-pill {
          display: inline-flex;
          align-items: center;
          gap: 0.45rem;
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 999px;
          padding: 0.48rem 0.72rem;
          background: rgba(13, 19, 27, 0.86);
          color: var(--traidr-text);
          font-size: 0.86rem;
          white-space: nowrap;
        }
        .traidr-pill strong { color: var(--traidr-green); font-weight: 700; }
        .traidr-panel {
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 8px;
          background: linear-gradient(180deg, rgba(17, 25, 35, 0.96), rgba(10, 15, 22, 0.98));
          padding: 1rem;
          box-shadow: 0 18px 60px rgba(0,0,0,0.22);
        }
        .traidr-panel h3 {
          margin: 0 0 0.35rem;
          font-size: 1rem;
          text-transform: uppercase;
          color: var(--traidr-text);
        }
        .traidr-panel p { margin: 0; color: var(--traidr-muted); }
        .traidr-mission-list {
          display: grid;
          gap: 0.55rem;
        }
        .traidr-mission-item {
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 0.65rem;
          align-items: start;
          padding: 0.65rem;
          border: 1px solid rgba(148, 163, 184, 0.14);
          border-radius: 8px;
          background: rgba(4, 8, 13, 0.58);
        }
        .traidr-dot {
          width: 0.72rem;
          height: 0.72rem;
          border-radius: 50%;
          margin-top: 0.22rem;
          background: var(--traidr-blue);
          box-shadow: 0 0 0 3px rgba(106, 167, 255, 0.12);
        }
        .traidr-dot.complete {
          background: var(--traidr-green);
          box-shadow: 0 0 0 3px rgba(83, 224, 107, 0.12);
        }
        .traidr-dot.missing {
          background: var(--traidr-red);
          box-shadow: 0 0 0 3px rgba(255, 77, 85, 0.12);
        }
        .traidr-command-card {
          min-height: 8.5rem;
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 8px;
          background: linear-gradient(180deg, rgba(17, 25, 35, 0.96), rgba(8, 13, 19, 0.98));
          padding: 0.9rem;
          margin-bottom: 0.65rem;
        }
        .traidr-command-card h4 {
          margin: 0 0 0.35rem;
          font-size: 1rem;
        }
        .traidr-command-card p {
          margin: 0.2rem 0;
          color: var(--traidr-muted);
          font-size: 0.86rem;
          line-height: 1.35;
        }
        .traidr-accent-cyan { border-color: rgba(32, 217, 255, 0.42); }
        .traidr-accent-green { border-color: rgba(83, 224, 107, 0.42); }
        .traidr-accent-red { border-color: rgba(255, 77, 85, 0.42); }
        .traidr-accent-blue { border-color: rgba(106, 167, 255, 0.42); }
        .traidr-result {
          border: 1px solid rgba(83, 224, 107, 0.26);
          border-radius: 8px;
          padding: 0.8rem;
          background: rgba(18, 83, 52, 0.12);
          margin: 0.6rem 0 1rem;
        }
        .traidr-result.failed {
          border-color: rgba(255, 77, 85, 0.32);
          background: rgba(95, 20, 29, 0.16);
        }
        .traidr-empty {
          border: 1px dashed rgba(148, 163, 184, 0.30);
          border-radius: 8px;
          padding: 1rem;
          background: rgba(13, 19, 27, 0.62);
          color: var(--traidr-muted);
        }
        .traidr-static-chart {
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 8px;
          background: #080b10;
          overflow: hidden;
          box-shadow: 0 18px 60px rgba(0,0,0,0.28);
        }
        .traidr-static-chart-empty {
          min-height: 28rem;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 2rem;
          color: var(--traidr-muted);
          text-align: center;
        }
        .traidr-static-chart-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 1rem;
          padding: 0.75rem 0.9rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.18);
          color: var(--traidr-text);
          font-size: 0.9rem;
        }
        .traidr-static-chart-header span {
          margin-left: 0.55rem;
          color: var(--traidr-muted);
        }
        .traidr-candlestick-chart {
          display: block;
          width: 100%;
          min-height: 32rem;
          font-family: Inter, system-ui, sans-serif;
        }
        .traidr-sidebar-brand {
          border: 1px solid rgba(32, 217, 255, 0.28);
          border-radius: 8px;
          padding: 0.9rem;
          background: rgba(4, 8, 13, 0.68);
          margin-bottom: 1rem;
        }
        .traidr-sidebar-brand h2 {
          margin: 0;
          font-size: 1.45rem;
        }
        .traidr-sidebar-brand p {
          margin: 0.3rem 0 0;
          color: var(--traidr-cyan);
        }
        .traidr-safety-list {
          display: grid;
          gap: 0.45rem;
          font-size: 0.9rem;
        }
        .traidr-safety-row {
          display: flex;
          justify-content: space-between;
          border-bottom: 1px solid rgba(148, 163, 184, 0.12);
          padding-bottom: 0.35rem;
        }
        .traidr-safety-row span:last-child { color: var(--traidr-green); font-weight: 700; }
        @media (max-width: 900px) {
          .traidr-shell-header { align-items: flex-start; flex-direction: column; }
          .traidr-status-row { justify-content: flex-start; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_command_center_header(data: DashboardData) -> None:
    """Render the primary app header and safety status chips."""

    health = build_dashboard_health(data)
    db_class = "strong" if data.database_exists else "span"
    st.markdown(
        f"""
        <div class="traidr-shell-header">
          <div class="traidr-title">
            <h1>TRAIDR Command Center</h1>
            <p>Your local crypto intelligence cockpit. Research only, simulation-first, no live execution.</p>
          </div>
          <div class="traidr-status-row">
            <span class="traidr-pill">Research only</span>
            <span class="traidr-pill">can_execute_trades: <strong>false</strong></span>
            <span class="traidr-pill">DuckDB: <{db_class}>{escape(health.database_label)}</{db_class}></span>
            <span class="traidr-pill">Safety: <strong>On</strong></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_status(data: DashboardData) -> None:
    """Render a concise branded sidebar status block."""

    health = build_dashboard_health(data)
    st.sidebar.markdown(
        f"""
        <div class="traidr-sidebar-brand">
          <h2>TRAIDR</h2>
          <p>Command Center</p>
        </div>
        <div class="traidr-panel">
          <h3>Safety Status</h3>
          <div class="traidr-safety-list">
            <div class="traidr-safety-row"><span>Live trading</span><span>false</span></div>
            <div class="traidr-safety-row"><span>Withdrawals</span><span>false</span></div>
            <div class="traidr-safety-row"><span>Private keys</span><span>false</span></div>
            <div class="traidr-safety-row"><span>AI execution</span><span>false</span></div>
            <div class="traidr-safety-row"><span>Simulation only</span><span>true</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"DuckDB: {health.database_label} · {health.table_count} tables")
    st.sidebar.caption("Research only. Not financial advice.")


def render_daily_mission(data: DashboardData) -> None:
    """Render the daily mission checklist."""

    items = build_daily_mission(data)
    rows = []
    for item in items:
        rows.append(
            f"""
            <div class="traidr-mission-item">
              <span class="traidr-dot {escape(item.state)}"></span>
              <div>
                <strong>{escape(item.label)}</strong>
                <p>{escape(item.detail)}</p>
              </div>
            </div>
            """
        )
    st.markdown(
        f"""
        <div class="traidr-panel">
          <h3>Daily Mission</h3>
          <p>Start here when you open TRAIDR. Buttons below are local, allowlisted, and non-executing.</p>
          <div class="traidr-mission-list">{''.join(rows)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_setup_instructions(database_path: str) -> None:
    """Show friendly setup instructions when the local database is absent."""

    render_empty_state(
        "No local DuckDB database yet",
        "Run Daily Workflow, Fixture Scan, or Paper Simulation from Operations to create local research evidence.",
        "You can also use the setup commands below.",
    )
    st.code(
        f"python scripts/run_simulation.py --database {database_path}\n"
        "python -m streamlit run dashboard/app.py",
        language="bash",
    )


def render_safety_status(data: DashboardData) -> None:
    """Render static safety posture from local config."""

    st.subheader("Safety Status")
    safety = data.safety_status
    columns = st.columns(4)
    columns[0].metric("Mode", str(safety.get("runtime_mode")))
    columns[1].metric("Live Trading", _yes_no(safety.get("live_trading_implemented")))
    columns[2].metric("Withdrawals", _yes_no(safety.get("withdrawals_implemented")))
    columns[3].metric("LLM Execution", _yes_no(safety.get("llm_direct_order_execution_allowed")))
    render_table(
        "Safety Config",
        [
            {"setting": key, "value": value}
            for key, value in sorted(safety.items())
        ],
    )


def render_database_summary(data: DashboardData) -> None:
    """Render a compact local database summary."""

    st.subheader("Local Database")
    st.write(f"Path: `{data.database_path}`")
    st.write(f"Tables: {', '.join(sorted(data.tables)) if data.tables else 'none'}")


def render_command_strip(database_path: str, *, key_prefix: str = "strip") -> None:
    """Render the compact cockpit command strip."""

    st.subheader("Command Strip")
    st.caption("Research-only buttons. No live trading, no withdrawals, no private-key access.")
    cards = build_command_cards()
    columns = st.columns(3)
    for index, card in enumerate(cards):
        with columns[index % 3]:
            _render_command_card(card)
            _render_action_button(card, database_path, key_prefix=key_prefix)


def render_command_center(database_path: str, *, key_prefix: str = "operations") -> None:
    """Render safe local action buttons for daily operator workflows."""

    st.subheader("Command Center")
    st.caption("Operate TRAIDR from buttons instead of terminal commands. Every action is allowlisted and local.")
    cards = build_command_cards()
    columns = st.columns(3)
    for index, card in enumerate(cards):
        with columns[index % 3]:
            _render_command_card(card)
            _render_action_button(card, database_path, key_prefix=key_prefix)


def render_risk_first_tables(
    risk_title: str,
    risk_rows: Sequence[Mapping[str, Any]],
    opportunity_title: str,
    opportunity_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Render risk evidence before opportunity evidence."""

    render_table(risk_title, risk_rows)
    render_table(opportunity_title, opportunity_rows)


def render_table(title: str, rows: Sequence[Mapping[str, Any]]) -> None:
    """Render a read-only table section with empty-state handling."""

    st.subheader(title)
    if not rows:
        render_empty_state(
            title,
            "No local rows found yet.",
            "Run Daily Workflow or a relevant scan from Operations to create read-only evidence.",
        )
        return
    st.dataframe([_display_row(row) for row in rows], width="stretch", hide_index=True)


def render_empty_state(title: str, body: str, next_action: str) -> None:
    """Render an empty state that points to the next safe action."""

    st.markdown(
        f"""
        <div class="traidr-empty">
          <strong>{escape(title)}</strong>
          <p>{escape(body)}</p>
          <p>{escape(next_action)}</p>
          <p>can_execute_trades: false</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_command_card(card: CommandCard) -> None:
    st.markdown(
        f"""
        <div class="traidr-command-card traidr-accent-{escape(card.accent)}">
          <h4>{escape(card.label)}</h4>
          <p>{escape(card.description)}</p>
          <p>{escape(card.detail)}</p>
          <p>can_execute_trades: false</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_action_button(card: CommandCard, database_path: str, *, key_prefix: str) -> None:
    key = f"dashboard_action_{key_prefix}_{card.action}"
    if st.button(card.button_label, key=key, width="stretch"):
        with st.spinner(f"Running {card.label}..."):
            result = run_dashboard_action(card.action, database=database_path)
        failed = result.exit_code != 0
        summary_lines = summarize_action_output(result.output)
        summary = "".join(f"<li>{escape(line)}</li>" for line in summary_lines)
        st.markdown(
            f"""
            <div class="traidr-result {'failed' if failed else ''}">
              <strong>{escape(result.label)} {'failed safely' if failed else 'completed'}</strong>
              <ul>{summary}</ul>
              <p>can_execute_trades: {str(result.can_execute_trades).lower()}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Raw local output"):
            st.code(result.output, language="text")
        st.info("Refresh the app data after actions that write DuckDB evidence.")


def _yes_no(value: Any) -> str:
    return "yes" if value is True else "no"


def _display_row(row: Mapping[str, Any]) -> dict[str, Any]:
    display: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list, tuple, set)):
            display[key] = str(value)
        elif isinstance(value, bool):
            display[key] = "false" if value is False else "true"
        elif value is None:
            display[key] = ""
        else:
            display[key] = str(value)
    return display
