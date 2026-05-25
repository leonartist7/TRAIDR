from sentiment.scorer import score_sentiment_snippets


def test_sentiment_scorer_penalizes_spam_confidence() -> None:
    clean = score_sentiment_snippets(["$ABC breakout momentum", "partnership launch"])
    spam = score_sentiment_snippets(["$ABC moon 100x", "$ABC moon 100x"])

    assert clean.status == "OK"
    assert spam.confidence < clean.confidence
    assert spam.can_execute_trades is False


def test_sentiment_missing_is_insufficient_not_bullish() -> None:
    score = score_sentiment_snippets([])

    assert score.status == "INSUFFICIENT_DATA"
    assert score.score == 0.0
