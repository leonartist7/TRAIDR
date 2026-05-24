"""Technical vector scoring agent; structured analysis only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, insufficient_analysis, make_analysis, numeric


class TechnicalAgent:
    name = "technical"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        momentum = numeric(context, "technical_momentum")
        if momentum is None:
            return insufficient_analysis(self.name, "TECHNICAL_DATA_MISSING", "technical vector missing")
        return make_analysis(
            agent=self.name,
            score=(momentum + 1) * 50,
            risk_score=60 if momentum < -0.4 else 20,
            confidence=0.7,
            status="OK",
            reason_codes=("TECHNICAL_VECTOR_AVAILABLE",),
            summary="technical momentum scored from local vector",
        )
