"""Read-only news source contracts and fixture loader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from intelligence.news_scoring import score_news_items


@dataclass(frozen=True)
class NewsItem:
    headline: str
    source: str
    observed_at: datetime
    sentiment: float | None
    impact: float
    categories: tuple[str, ...]
    url: str | None = None
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "source": self.source,
            "observed_at": self.observed_at.isoformat(),
            "sentiment": self.sentiment,
            "impact": self.impact,
            "categories": list(self.categories),
            "url": self.url,
            "can_execute_trades": self.can_execute_trades,
        }


@dataclass(frozen=True)
class NewsSourceResult:
    status: str
    items: tuple[NewsItem, ...]
    score: dict[str, Any]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "items": [item.to_dict() for item in self.items],
            "score": self.score,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }


FIXTURE_NEWS = (
    {
        "headline": "Solana ecosystem project announces product partnership",
        "source": "fixture_news",
        "sentiment": 0.45,
        "impact": 2.0,
        "observed_at": "2026-05-22T12:00:00+00:00",
    },
    {
        "headline": "Market-wide fear rises after exploit rumors",
        "source": "fixture_news",
        "sentiment": -0.65,
        "impact": 2.5,
        "observed_at": "2026-05-22T12:01:00+00:00",
    },
)


def fixture_news_result() -> NewsSourceResult:
    return build_news_result(FIXTURE_NEWS, source_name="fixture_news")


def build_news_result(raw_items: tuple[dict[str, Any], ...] | list[dict[str, Any]], *, source_name: str) -> NewsSourceResult:
    items = tuple(_coerce_item(row, source_name=source_name) for row in raw_items)
    items = tuple(item for item in items if item is not None)
    if not items:
        score = score_news_items(())
        return NewsSourceResult("INSUFFICIENT_DATA", (), score.to_dict(), ("NEWS_SOURCE_ITEMS_MISSING",))
    score = score_news_items(tuple(item.to_dict() for item in items))
    status = "OK" if score.classification != "INSUFFICIENT_DATA" else "INSUFFICIENT_DATA"
    source_reason = "NEWS_SOURCE_OK" if status == "OK" else "NEWS_SOURCE_NON_ACTIONABLE"
    return NewsSourceResult(status, items, score.to_dict(), (source_reason, *score.reason_codes))


def classify_news_text(text: str) -> tuple[float | None, float, tuple[str, ...]]:
    lower = text.lower()
    categories: list[str] = []
    sentiment = 0.0
    impact = 1.0
    if any(word in lower for word in ("hack", "exploit", "drain", "stolen")):
        categories.append("HACK_EXPLOIT_RISK")
        sentiment -= 0.8
        impact = max(impact, 3.0)
    if "delist" in lower or "delisting" in lower:
        categories.append("DELISTING_RISK")
        sentiment -= 0.7
        impact = max(impact, 2.5)
    if any(word in lower for word in ("sec", "regulation", "lawsuit", "ban")):
        categories.append("REGULATION_RISK")
        sentiment -= 0.5
        impact = max(impact, 2.0)
    if any(word in lower for word in ("fear", "risk-off", "selloff", "panic")):
        categories.append("MARKET_WIDE_RISK_OFF")
        sentiment -= 0.45
        impact = max(impact, 2.0)
    if any(word in lower for word in ("listing", "listed", "exchange lists")) and "delist" not in lower:
        categories.append("LISTING_NEWS")
        sentiment += 0.55
        impact = max(impact, 2.0)
    if any(word in lower for word in ("partnership", "product", "launch", "integration")):
        categories.append("PARTNERSHIP_PRODUCT_NEWS")
        sentiment += 0.35
        impact = max(impact, 1.5)
    if not categories:
        categories.append("NEWS_UNCLASSIFIED")
        return None, impact, tuple(categories)
    return max(-1.0, min(1.0, sentiment)), impact, tuple(categories)


def _coerce_item(row: dict[str, Any], *, source_name: str) -> NewsItem | None:
    headline = str(row.get("headline") or row.get("title") or "").strip()
    if not headline:
        return None
    sentiment = row.get("sentiment")
    impact = row.get("impact", 1.0)
    categories = row.get("categories")
    if sentiment is None or categories is None:
        sentiment, impact, categories = classify_news_text(headline)
    observed_at = row.get("observed_at") or datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(str(observed_at))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return NewsItem(
        headline=headline,
        source=str(row.get("source") or source_name),
        observed_at=parsed.astimezone(timezone.utc),
        sentiment=float(sentiment) if sentiment is not None else None,
        impact=float(impact),
        categories=tuple(str(category) for category in categories),
        url=str(row["url"]) if row.get("url") else None,
    )
