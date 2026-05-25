"""Local sentiment-lite feature extraction."""

from __future__ import annotations

import re

from sentiment.contracts import SentimentFeatures
from sentiment.spam_filter import spam_repetition_score

_POSITIVE = ("breakout", "momentum", "partnership", "launch", "listed", "accumulating", "bullish")
_NEGATIVE = ("warning", "dump", "bearish", "risk", "selloff", "unlock", "liquidity drain")
_SCAM = ("scam", "rug", "honeypot", "fake", "phishing", "drainer")
_TICKER_RE = re.compile(r"\$[A-Za-z][A-Za-z0-9_]{1,12}\b")


def extract_sentiment_features(snippets: tuple[str, ...] | list[str] | None) -> SentimentFeatures:
    if not snippets:
        return SentimentFeatures(0, 0, 0, 0, (), 0, ("SENTIMENT_SNIPPETS_MISSING",))
    rows = tuple(str(snippet) for snippet in snippets if str(snippet).strip())
    if not rows:
        return SentimentFeatures(0, 0, 0, 0, (), 0, ("SENTIMENT_SNIPPETS_MISSING",))
    lower_rows = [row.lower() for row in rows]
    positive = sum(any(word in row for word in _POSITIVE) for row in lower_rows)
    negative = sum(any(word in row for word in _NEGATIVE) for row in lower_rows)
    scam = sum(any(word in row for word in _SCAM) for row in lower_rows)
    tickers = tuple(dict.fromkeys(match.upper() for row in rows for match in _TICKER_RE.findall(row)))
    spam = spam_repetition_score(rows)
    reasons = ["SENTIMENT_FEATURES_EXTRACTED"]
    if spam:
        reasons.append("SPAM_OR_SHILL_REPETITION")
    if scam:
        reasons.append("SCAM_LANGUAGE_DETECTED")
    return SentimentFeatures(positive, negative, scam, spam, tickers, len(rows), tuple(reasons))
