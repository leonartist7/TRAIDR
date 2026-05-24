"""Macro backdrop scoring agent; analysis only, no execution authority."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, insufficient_analysis, make_analysis, numeric


class MacroAgent:
    name = "macro"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        risk_appetite = numeric(context, "macro_risk_appetite")
        if risk_appetite is None:
            return insufficient_analysis(self.name, "MACRO_DATA_MISSING", "macro backdrop unknown")
        score = risk_appetite * 100
        risk = (1 - risk_appetite) * 60
        return make_analysis(
            agent=self.name,
            score=score,
            risk_score=risk,
            confidence=0.65,
            status="OK",
            reason_codes=("MACRO_CONTEXT_AVAILABLE",),
            summary="macro risk appetite scored from local context",
        )
