"""Generic read-only crypto news adapter with injectable transport."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from intelligence.news_sources import NewsSourceResult, build_news_result

Transport = Callable[[], Mapping[str, Any] | list[Mapping[str, Any]] | None]


class CryptoNewsAdapter:
    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport

    def fetch(self) -> NewsSourceResult:
        if self.transport is None:
            return NewsSourceResult("INSUFFICIENT_DATA", (), {}, ("CRYPTO_NEWS_TRANSPORT_UNAVAILABLE",))
        try:
            payload = self.transport()
        except Exception:
            return NewsSourceResult("INSUFFICIENT_DATA", (), {}, ("CRYPTO_NEWS_FETCH_FAILED",))
        if payload is None:
            return NewsSourceResult("INSUFFICIENT_DATA", (), {}, ("CRYPTO_NEWS_SOURCE_MISSING",))
        if isinstance(payload, Mapping):
            rows = payload.get("items") or payload.get("data") or []
        else:
            rows = payload
        if not isinstance(rows, list):
            return NewsSourceResult("INSUFFICIENT_DATA", (), {}, ("CRYPTO_NEWS_SHAPE_INVALID",))
        return build_news_result(rows, source_name="crypto_news")
