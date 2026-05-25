"""Score local sentiment-lite features conservatively."""

from __future__ import annotations

from sentiment.contracts import SentimentFeatures, SentimentScore
from sentiment.features import extract_sentiment_features


def score_sentiment_snippets(snippets: tuple[str, ...] | list[str] | None) -> SentimentScore:
    features = extract_sentiment_features(snippets)
    if features.snippet_count == 0:
        return SentimentScore(
            "INSUFFICIENT_DATA",
            0.0,
            0.0,
            features,
            ("SENTIMENT_INSUFFICIENT_DATA",),
        )
    raw = features.positive_momentum * 20 - features.negative_warnings * 20 - features.scam_language * 40
    score = max(-100.0, min(100.0, float(raw)))
    confidence = min(1.0, features.snippet_count / 5)
    if features.spam_repetition:
        confidence = max(0.0, confidence - min(0.5, features.spam_repetition / 200))
    if features.scam_language:
        confidence = max(0.0, confidence - 0.2)
    reasons = ["SENTIMENT_SCORED"]
    reasons.extend(reason for reason in features.reason_codes if reason != "SENTIMENT_FEATURES_EXTRACTED")
    status = "OK" if confidence > 0 else "INSUFFICIENT_DATA"
    return SentimentScore(status, score, round(confidence, 4), features, tuple(dict.fromkeys(reasons)))
