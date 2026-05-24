from intelligence.news_scoring import score_news_items


def test_news_scoring_classifies_bearish_news() -> None:
    score = score_news_items(
        [
            {"sentiment": -0.8, "impact": 3},
            {"sentiment": -0.4, "impact": 1},
        ]
    )

    assert score.classification == "BEARISH_NEWS"
    assert "NEWS_RISK_OFF" in score.reason_codes


def test_news_scoring_missing_sentiment_fails_closed() -> None:
    score = score_news_items([{"headline": "unknown"}])

    assert score.classification == "INSUFFICIENT_DATA"

