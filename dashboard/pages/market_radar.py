"""Market radar and scan evidence dashboard page."""

from __future__ import annotations

import streamlit as st

from dashboard.components import render_risk_first_tables, render_table
from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    st.header("Market Radar")
    st.caption("Live research signals are ranked by opportunity minus risk. Percentages appear only after calibration gates pass.")
    signal_rows = []
    for row in data.signal_decisions:
        display = dict(row)
        probability = display.get("success_probability")
        display["probability"] = (
            f"{float(probability):.1%}"
            if probability is not None and display.get("probability_state") == "CALIBRATED"
            else "uncalibrated"
        )
        display["rank_value"] = float(display.get("opportunity_score") or 0) - float(display.get("risk_score") or 0)
        signal_rows.append(display)
    render_table("Current LONG / SHORT / NO_TRADE Decisions", signal_rows)

    if signal_rows:
        selected = signal_rows[0]
        st.subheader(f"Top Candidate · {selected.get('instrument_id')} · {selected.get('horizon')}")
        detail = selected.get("decision_json")
        if isinstance(detail, str):
            import json

            try:
                st.json(json.loads(detail))
            except json.JSONDecodeError:
                st.write("Decision detail is malformed and therefore non-actionable.")

    st.subheader("Evidence and Feature Contributions")
    render_table("Evidence Bundles", data.evidence_bundles)
    render_table("Multi-Horizon Features and Contradictions", data.feature_snapshots)
    render_table("Order Book and Aggressive Flow", data.market_microstructure)
    render_table("News Context (never directional alone)", data.news_evidence)
    render_table("On-Chain Safety Evidence", data.onchain_evidence)
    render_table("Decision Change Audit", data.decision_audit)

    st.subheader("Legacy Radar (fresh, deduplicated, non-fixture only)")
    risk_rows = sorted(data.market_radar, key=lambda row: float(row.get("risk_score") or 0), reverse=True)
    opportunity_rows = sorted(data.market_radar, key=lambda row: float(row.get("opportunity_score") or 0), reverse=True)
    render_risk_first_tables("Highest Risks", risk_rows, "Best Opportunities", opportunity_rows)

    st.header("Scan Evidence")
    render_table("Latest Scan Evidence", data.scan_evidence)
