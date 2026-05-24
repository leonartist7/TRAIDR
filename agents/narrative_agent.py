"""Narrative scoring agent; local structured analysis only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, insufficient_analysis, make_analysis, numeric


class NarrativeAgent:
    name = "narrative"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        strength = numeric(context, "narrative_strength")
        if strength is None:
            return insufficient_analysis(self.name, "NARRATIVE_DATA_MISSING", "narrative evidence missing")
        return make_analysis(
            agent=self.name,
            score=strength,
            risk_score=15 if strength >= 60 else 35,
            confidence=0.55,
            status="OK",
            reason_codes=("NARRATIVE_CONTEXT_AVAILABLE",),
            summary="narrative strength scored from local context",
        )
