from intelligence.news_scoring import score_news_items
from intelligence.news_sources import build_news_result, classify_news_text, fixture_news_result


def test_fixture_news_works_offline_and_is_non_executing() -> None:
    result = fixture_news_result()

    assert result.status == "OK"
    assert result.can_execute_trades is False
    assert result.items


def test_news_classification_detects_required_categories() -> None:
    headlines = [
        "Protocol suffers exploit hack",
        "Token listing announced",
        "Exchange delisting warning",
        "SEC regulation lawsuit risk",
        "Product partnership launch",
        "Market-wide fear risk-off panic",
    ]
    categories = set()
    for headline in headlines:
        _sentiment, _impact, found = classify_news_text(headline)
        categories.update(found)

    assert "HACK_EXPLOIT_RISK" in categories
    assert "LISTING_NEWS" in categories
    assert "DELISTING_RISK" in categories
    assert "REGULATION_RISK" in categories
    assert "PARTNERSHIP_PRODUCT_NEWS" in categories
    assert "MARKET_WIDE_RISK_OFF" in categories


def test_missing_news_is_insufficient_not_bullish() -> None:
    score = score_news_items([])

    assert score.classification == "INSUFFICIENT_DATA"
    assert score.confidence == 0.0


def test_news_result_carries_category_reason_codes() -> None:
    result = build_news_result(
        [{"headline": "Major exploit hack drains bridge", "source": "fixture"}],
        source_name="fixture",
    )

    assert result.score["classification"] == "BEARISH_NEWS"
    assert "HACK_EXPLOIT_RISK" in result.score["reason_codes"]
