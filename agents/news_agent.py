"""News scoring agent; structured local analysis only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, insufficient_analysis, make_analysis, numeric


class NewsAgent:
    name = "news"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        sentiment = numeric(context, "news_sentiment")
        if sentiment is None:
            return insufficient_analysis(self.name, "NEWS_DATA_MISSING", "news context missing")
        risk = 70 if sentiment < -0.5 else 20
        return make_analysis(
            agent=self.name,
            score=(sentiment + 1) * 50,
            risk_score=risk,
            confidence=0.6,
            status="OK",
            reason_codes=("NEWS_CONTEXT_AVAILABLE",),
            summary="news sentiment scored from local context",
        )
