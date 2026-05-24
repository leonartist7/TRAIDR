"""Read-only DexScreener market wrapper."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from data_pipeline.contracts import AdapterResult, NormalizedMarketSnapshot
from data_pipeline.normalization import normalize_market_record

Transport = Callable[[str], Mapping[str, Any] | None]

DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex/pairs"


class DexScreenerHTTPError(RuntimeError):
    """Raised when the read-only DexScreener HTTP request fails."""


class DexScreenerAdapter:
    name = "dexscreener"

    def __init__(self, transport: Transport | None = None, *, now: datetime | None = None) -> None:
        self.transport = transport
        self.now = now

    def fetch_snapshot(self, pair_ref: str) -> AdapterResult[NormalizedMarketSnapshot]:
        if self.transport is None:
            return AdapterResult.insufficient("DEXSCREENER_TRANSPORT_UNAVAILABLE")
        try:
            raw = self.transport(pair_ref)
        except DexScreenerHTTPError:
            return AdapterResult.insufficient("DEXSCREENER_HTTP_ERROR")
        except Exception:
            return AdapterResult.insufficient("DEXSCREENER_TRANSPORT_FAILED")
        if raw is None:
            return AdapterResult.insufficient("DEXSCREENER_SOURCE_MISSING")
        mapped = _map_dexscreener_payload(raw, pair_ref, observed_at=self.now)
        return normalize_market_record(mapped, source_name=self.name, now=self.now)


def default_dexscreener_transport(pair_ref: str) -> Mapping[str, Any] | None:
    """Fetch one DexScreener pair response using a read-only public endpoint."""

    chain_id, pair_address = _split_pair_ref(pair_ref)
    request = Request(
        f"{DEXSCREENER_BASE_URL}/{chain_id}/{pair_address}",
        headers={"User-Agent": "TRAIDR-read-only-scan/0.1"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise DexScreenerHTTPError(f"DexScreener HTTP status {status}")
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise DexScreenerHTTPError("DexScreener request failed") from exc


def _map_dexscreener_payload(
    raw: Mapping[str, Any],
    pair_ref: str,
    *,
    observed_at: datetime | None,
) -> dict[str, Any]:
    if "pair_id" in raw:
        return dict(raw)
    pair = _select_pair(raw, pair_ref)
    if pair is None:
        return {}
    base_token = _mapping(pair.get("baseToken"))
    quote_token = _mapping(pair.get("quoteToken"))
    liquidity = _mapping(pair.get("liquidity"))
    volume = _mapping(pair.get("volume"))
    fallback_observed_at = observed_at or datetime.now(timezone.utc)
    return {
        "pair_id": _first(pair.get("pairAddress"), pair.get("pair_id"), pair_ref),
        "chain_id": _first(pair.get("chainId"), pair.get("chain_id"), _chain_from_ref(pair_ref)),
        "base_symbol": _first(base_token.get("symbol"), pair.get("base_symbol")),
        "quote_symbol": _first(quote_token.get("symbol"), pair.get("quote_symbol"), "USD"),
        "price_usd": _first(pair.get("priceUsd"), pair.get("price_usd")),
        "liquidity_usd": _first(liquidity.get("usd"), pair.get("liquidity_usd")),
        "volume_24h_usd": _first(volume.get("h24"), pair.get("volume_24h_usd")),
        "observed_at": _first(
            pair.get("observed_at"),
            pair.get("updatedAt"),
            pair.get("lastUpdated"),
            fallback_observed_at.isoformat(),
        ),
        "source_record_id": _first(pair.get("url"), pair.get("pairAddress"), pair_ref),
        "raw_status": _first(pair.get("raw_status"), "dexscreener"),
    }


def _select_pair(raw: Mapping[str, Any], pair_ref: str) -> Mapping[str, Any] | None:
    if isinstance(raw.get("pairs"), list):
        pairs = [pair for pair in raw["pairs"] if isinstance(pair, Mapping)]
        if not pairs:
            return None
        chain_id, pair_address = _split_pair_ref(pair_ref)
        for pair in pairs:
            if (
                str(pair.get("chainId", "")).lower() == chain_id.lower()
                and str(pair.get("pairAddress", "")).lower() == pair_address.lower()
            ):
                return pair
        return pairs[0]
    if isinstance(raw.get("pair"), Mapping):
        return raw["pair"]
    if "pairAddress" in raw:
        return raw
    return None


def _split_pair_ref(pair_ref: str) -> tuple[str, str]:
    parts = pair_ref.split("/", 1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise DexScreenerHTTPError("pair ref must use chain/pairAddress")
    return parts[0].strip(), parts[1].strip()


def _chain_from_ref(pair_ref: str) -> str | None:
    try:
        return _split_pair_ref(pair_ref)[0]
    except DexScreenerHTTPError:
        return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None
