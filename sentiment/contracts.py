"""Contracts for local sentiment-lite features."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SentimentFeatures:
    positive_momentum: int
    negative_warnings: int
    scam_language: int
    spam_repetition: int
    ticker_mentions: tuple[str, ...]
    snippet_count: int
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "positive_momentum": self.positive_momentum,
            "negative_warnings": self.negative_warnings,
            "scam_language": self.scam_language,
            "spam_repetition": self.spam_repetition,
            "ticker_mentions": list(self.ticker_mentions),
            "snippet_count": self.snippet_count,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }


@dataclass(frozen=True)
class SentimentScore:
    status: str
    score: float
    confidence: float
    features: SentimentFeatures
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "confidence": self.confidence,
            "features": self.features.to_dict(),
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }
