"""Read-only live scanner view with factor-level explanations."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from dashboard.queries import DashboardData


def render(data: DashboardData) -> None:
    """Render persisted scanner scores without exposing execution controls."""

    st.subheader("Live market scanner")
    st.caption(
        "Research-only scores from public market data. Every factor is shown; missing or "
        "conflicting evidence keeps the result at NO_TRADE or INSUFFICIENT_DATA."
    )
    if not data.scanner_scores:
        st.info(
            "No scanner snapshot is stored yet. Start the local research service and "
            "allow one analysis cycle to complete."
        )
        return

    for row in data.scanner_scores:
        instrument_id = str(row.get("instrument_id", "unknown"))
        status = str(row.get("status", "INSUFFICIENT_DATA"))
        direction = str(row.get("direction", "NO_TRADE"))
        score = row.get("score")
        risk_score = row.get("risk_score")
        st.markdown(f"### {instrument_id} · {direction}")
        columns = st.columns(4)
        columns[0].metric("State", status)
        columns[1].metric("Score", _format_number(score))
        columns[2].metric("Long", _format_number(row.get("long_score")))
        columns[3].metric("Risk", _format_number(risk_score))

        conflicts = _json_list(row.get("conflicts_json"))
        reasons = _json_list(row.get("reason_codes_json"))
        if conflicts:
            st.warning("Source conflicts: " + ", ".join(str(item) for item in conflicts))
        if reasons:
            st.caption("Reasons: " + ", ".join(str(item) for item in reasons))

        factors = _json_list(row.get("factor_breakdown_json"))
        if factors:
            st.dataframe(
                factors,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "factor": "Factor",
                    "weight": st.column_config.NumberColumn("Weight", format="%.1f"),
                    "raw_value": st.column_config.NumberColumn("Raw", format="%.6f"),
                    "normalized_value": st.column_config.NumberColumn("Normalized", format="%.3f"),
                    "long_contribution": st.column_config.NumberColumn("Long contribution", format="%.3f"),
                    "short_contribution": st.column_config.NumberColumn("Short contribution", format="%.3f"),
                    "explanation": "Why it contributed",
                    "source": "Source",
                    "reason_codes": "Evidence status",
                },
            )
        else:
            st.info("No factor breakdown is available; the scanner failed closed.")


def _json_list(value: Any) -> list[dict[str, Any]] | list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    if not isinstance(value, str):
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return []
    return decoded if isinstance(decoded, list) else []


def _format_number(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)
