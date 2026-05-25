"""Narrative scoring agent; local structured analysis only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.agent_bus import AnalysisPayload, insufficient_analysis, make_analysis, numeric
from sentiment.scorer import score_sentiment_snippets


class NarrativeAgent:
    name = "narrative"

    def analyze(self, context: Mapping[str, Any]) -> AnalysisPayload:
        strength = numeric(context, "narrative_strength")
        sentiment = None
        if "sentiment_snippets" in context:
            raw_snippets = context.get("sentiment_snippets")
            snippets = tuple(raw_snippets) if isinstance(raw_snippets, (list, tuple)) else ()
            sentiment = score_sentiment_snippets(snippets)
            if sentiment.status == "OK":
                strength = max(strength or 0, 50 + sentiment.score / 2)
        if strength is None:
            return insufficient_analysis(self.name, "NARRATIVE_DATA_MISSING", "narrative evidence missing")
        confidence = 0.55
        reasons = ["NARRATIVE_CONTEXT_AVAILABLE"]
        if sentiment is not None:
            confidence = min(confidence, sentiment.confidence)
            reasons.extend(sentiment.reason_codes)
        return make_analysis(
            agent=self.name,
            score=strength,
            risk_score=15 if strength >= 60 else 35,
            confidence=confidence,
            status="OK",
            reason_codes=tuple(dict.fromkeys(reasons)),
            summary="narrative strength scored from local context",
        )
