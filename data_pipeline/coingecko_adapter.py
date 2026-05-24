"""Read-only CoinGecko market wrapper with injected transport only."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from data_pipeline.contracts import AdapterResult, NormalizedMarketSnapshot
from data_pipeline.normalization import normalize_market_record

Transport = Callable[[str], Mapping[str, Any] | None]


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
