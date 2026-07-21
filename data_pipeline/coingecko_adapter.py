"""Read-only CoinGecko keyless public market wrapper."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import json

from data_pipeline.contracts import AdapterResult, NormalizedMarketSnapshot
from data_pipeline.normalization import normalize_market_record

Transport = Callable[[str], Mapping[str, Any] | None]
COINGECKO_PUBLIC_BASE_URL = "https://api.coingecko.com/api/v3/coins"


class CoinGeckoAdapter:
    """Normalize mocked or injected CoinGecko-style payloads into snapshots."""

    name = "coingecko"

    def __init__(self, transport: Transport | None = None, *, now: datetime | None = None) -> None:
        self.transport = transport
        self.now = now

    def fetch_snapshot(self, pair_ref: str) -> AdapterResult[NormalizedMarketSnapshot]:
        if self.transport is None:
            return AdapterResult.insufficient("COINGECKO_TRANSPORT_UNAVAILABLE")
        try:
            raw = self.transport(pair_ref)
        except Exception:
            return AdapterResult.insufficient("COINGECKO_TRANSPORT_FAILED")
        if raw is None:
            return AdapterResult.insufficient("COINGECKO_SOURCE_MISSING")
        mapped = _map_coingecko_payload(raw, pair_ref)
        return normalize_market_record(mapped, source_name=self.name, now=self.now)


def default_coingecko_transport(coin_id: str) -> Mapping[str, Any] | None:
    """Fetch an exact reviewed CoinGecko coin id; callers must never pass a guessed symbol."""

    if not coin_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in coin_id):
        raise ValueError("CoinGecko transport requires an exact coin id")
    url = (
        f"{COINGECKO_PUBLIC_BASE_URL}/{quote(coin_id)}"
        "?localization=false&tickers=false&market_data=true&community_data=false"
        "&developer_data=false&sparkline=false"
    )
    request = Request(url, headers={"User-Agent": "TRAIDR-read-only-research/0.2"}, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            if getattr(response, "status", 200) >= 400:
                raise RuntimeError("CoinGecko public endpoint failed")
            parsed = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("CoinGecko keyless request failed") from exc
    return parsed if isinstance(parsed, Mapping) else None


def _map_coingecko_payload(raw: Mapping[str, Any], pair_ref: str) -> dict[str, Any]:
    market_data = _mapping(raw.get("market_data"))
    current_price = _mapping(market_data.get("current_price"))
    total_volume = _mapping(market_data.get("total_volume"))
    total_value_locked = _mapping(market_data.get("total_value_locked"))

    source_id = _first(raw.get("source_record_id"), raw.get("id"), pair_ref)
    symbol = str(_first(raw.get("base_symbol"), raw.get("symbol"), pair_ref)).upper()
    return {
        "pair_id": _first(raw.get("pair_id"), f"{source_id}-usd"),
        "chain_id": _first(raw.get("chain_id"), raw.get("asset_platform_id"), "coingecko"),
        "base_symbol": symbol,
        "quote_symbol": _first(raw.get("quote_symbol"), "USD"),
        "price_usd": _first(raw.get("price_usd"), current_price.get("usd")),
        "liquidity_usd": _first(raw.get("liquidity_usd"), total_value_locked.get("usd")),
        "volume_24h_usd": _first(raw.get("volume_24h_usd"), total_volume.get("usd")),
        "observed_at": _first(raw.get("observed_at"), raw.get("last_updated")),
        "source_record_id": source_id,
        "raw_status": _first(raw.get("raw_status"), "mocked"),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None
