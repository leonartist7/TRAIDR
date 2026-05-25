"""Read-only RSS news adapter with injectable transport."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from intelligence.news_sources import NewsSourceResult, build_news_result

Transport = Callable[[str], str | bytes]


def default_rss_transport(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "TRAIDR-read-only-news/0.1"}, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("RSS request failed") from exc


class RSSNewsAdapter:
    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport

    def fetch(self, url: str) -> NewsSourceResult:
        if self.transport is None:
            return NewsSourceResult("INSUFFICIENT_DATA", (), {}, ("RSS_TRANSPORT_UNAVAILABLE",))
        try:
            raw = self.transport(url)
            text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            items = _parse_rss(text)
        except Exception:
            return NewsSourceResult("INSUFFICIENT_DATA", (), {}, ("RSS_FETCH_FAILED",))
        return build_news_result(items, source_name="rss")


def _parse_rss(text: str) -> list[dict[str, Any]]:
    root = ElementTree.fromstring(text)
    rows: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        if title:
            rows.append({"headline": title, "url": link or None, "observed_at": pub_date or None})
    for item in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = (item.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link_node = item.find("{http://www.w3.org/2005/Atom}link")
        link = link_node.attrib.get("href") if link_node is not None else None
        updated = (item.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
        if title:
            rows.append({"headline": title, "url": link, "observed_at": updated or None})
    return rows
