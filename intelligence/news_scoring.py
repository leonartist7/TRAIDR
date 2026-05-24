"""Fixture-first news scoring for market intelligence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NewsScore:
    classification: str
    score: float
    confidence: float
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "score": self.score,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


def score_news_items(items: Iterable[Mapping[str, Any]]) -> NewsScore:
    rows = tuple(items)
    if not rows:
        return NewsScore("INSUFFICIENT_DATA", 0.0, 0.0, ("NEWS_ITEMS_MISSING",))

    sentiments = [_sentiment(row.get("sentiment")) for row in rows]
    impacts = [_impact(row.get("impact")) for row in rows]
    usable = [(sentiment, impact) for sentiment, impact in zip(sentiments, impacts) if sentiment is not None]
    if not usable:
        return NewsScore("INSUFFICIENT_DATA", 0.0, 0.0, ("NEWS_SENTIMENT_MISSING",))

    weighted_sum = sum(sentiment * impact for sentiment, impact in usable)
    total_weight = sum(impact for _sentiment_value, impact in usable)
    score = weighted_sum / total_weight if total_weight else 0.0
    confidence = min(1.0, len(usable) / len(rows))
    reasons: list[str] = []
    if len(usable) < len(rows):
        reasons.append("NEWS_PARTIAL_DATA")
        confidence = max(0.0, confidence - 0.15)
    if score >= 0.35:
        classification = "BULLISH_NEWS"
        reasons.append("NEWS_RISK_ON")
    elif score <= -0.35:
        classification = "BEARISH_NEWS"
        reasons.append("NEWS_RISK_OFF")
    else:
        classification = "NEUTRAL_NEWS"
        reasons.append("NEWS_NEUTRAL")
    return NewsScore(classification, round(score, 4), round(confidence, 4), tuple(reasons))


def _sentiment(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return min(1.0, max(-1.0, float(value)))


def _impact(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    return min(5.0, max(0.1, float(value)))

