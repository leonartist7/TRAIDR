from sentiment.features import extract_sentiment_features


def test_sentiment_features_detect_keywords_and_tickers() -> None:
    features = extract_sentiment_features(
        ["$BONK breakout momentum", "warning possible rug", "$BONK partnership launch"]
    )

    assert features.positive_momentum == 2
    assert features.negative_warnings == 1
    assert features.scam_language == 1
    assert "$BONK" in features.ticker_mentions
    assert features.can_execute_trades is False


def test_missing_sentiment_is_not_bullish() -> None:
    features = extract_sentiment_features(None)

    assert features.snippet_count == 0
    assert "SENTIMENT_SNIPPETS_MISSING" in features.reason_codes
