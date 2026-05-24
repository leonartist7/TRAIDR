"""Read-only DefiLlama market wrapper with injected transport only."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from data_pipeline.contracts import AdapterResult, NormalizedMarketSnapshot
from data_pipeline.normalization import normalize_market_record

Transport = Callable[[str], Mapping[str, Any] | None]


class DefiLlamaAdapter:
    """Normalize mocked or injected DefiLlama-style payloads into snapshots."""

    name = "defillama"

    def __init__(self, transport: Transport | None = None, *, now: datetime | None = None) -> None:
        self.transport = transport
        self.now = now

    def fetch_snapshot(self, pair_ref: str) -> AdapterResult[NormalizedMarketSnapshot]:
        if self.transport is None:
            return AdapterResult.insufficient("DEFILLAMA_TRANSPORT_UNAVAILABLE")
        try:
            raw = self.transport(pair_ref)
        except Exception:
            return AdapterResult.insufficient("DEFILLAMA_TRANSPORT_FAILED")
        if raw is None:
            return AdapterResult.insufficient("DEFILLAMA_SOURCE_MISSING")
        mapped = _map_defillama_payload(raw, pair_ref)
        return normalize_market_record(mapped, source_name=self.name, now=self.now)


def _map_defillama_payload(raw: Mapping[str, Any], pair_ref: str) -> dict[str, Any]:
    source_id = _first(raw.get("source_record_id"), raw.get("slug"), raw.get("id"), raw.get("name"), pair_ref)
    symbol = str(_first(raw.get("base_symbol"), raw.get("symbol"), source_id)).upper()
    return {
        "pair_id": _first(raw.get("pair_id"), f"{source_id}-usd"),
        "chain_id": _first(raw.get("chain_id"), raw.get("chain"), "defillama"),
        "base_symbol": symbol,
        "quote_symbol": _first(raw.get("quote_symbol"), "USD"),
        "price_usd": _first(raw.get("price_usd"), raw.get("priceUsd")),
        "liquidity_usd": _first(raw.get("liquidity_usd"), raw.get("liquidityUsd"), raw.get("tvl")),
        "volume_24h_usd": _first(
            raw.get("volume_24h_usd"),
            raw.get("volume24hUsd"),
            raw.get("volume24h"),
            raw.get("dailyVolume"),
        ),
        "observed_at": _coerce_observed_at(
            _first(raw.get("observed_at"), raw.get("lastUpdated"), raw.get("timestamp")),
        ),
        "source_record_id": source_id,
        "raw_status": _first(raw.get("raw_status"), "mocked"),
    }


def _coerce_observed_at(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC).isoformat()
    return value


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None
