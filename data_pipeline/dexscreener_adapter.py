"""Fixture-first DexScreener market wrapper with injected transport only."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from data_pipeline.contracts import AdapterResult, NormalizedMarketSnapshot
from data_pipeline.normalization import normalize_market_record

Transport = Callable[[str], Mapping[str, Any] | None]


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
        except Exception:
            return AdapterResult.insufficient("DEXSCREENER_TRANSPORT_FAILED")
        return normalize_market_record(raw, source_name=self.name, now=self.now)

