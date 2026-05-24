"""Optional read-only market loader for registered data adapters."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from data_pipeline.coingecko_adapter import CoinGeckoAdapter, Transport as CoinGeckoTransport
from data_pipeline.contracts import AdapterResult, NormalizedMarketSnapshot
from data_pipeline.defillama_adapter import DefiLlamaAdapter, Transport as DefiLlamaTransport
from data_pipeline.dexscreener_adapter import DexScreenerAdapter, Transport as DexScreenerTransport
from data_pipeline.source_registry import SourceRegistry


class LiveMarketLoader:
    """Load normalized snapshots from explicitly registered read-only sources."""

    def __init__(self, registry: SourceRegistry | None = None) -> None:
        self.registry = registry or SourceRegistry()

    def fetch(self, source_name: str, pair_ref: str) -> AdapterResult[NormalizedMarketSnapshot]:
        return self.registry.fetch(source_name, pair_ref)

    def first_available(
        self,
        pair_ref: str,
        source_names: Iterable[str],
    ) -> AdapterResult[NormalizedMarketSnapshot]:
        reasons: list[str] = []
        for source_name in source_names:
            result = self.fetch(source_name, pair_ref)
            if result.ok:
                return result
            reasons.extend(result.reason_codes)
        if not reasons:
            reasons.append("LIVE_MARKET_SOURCES_MISSING")
        return AdapterResult.insufficient("LIVE_MARKET_SOURCES_INSUFFICIENT", *tuple(reasons))

    @classmethod
    def from_optional_transports(
        cls,
        *,
        dexscreener_transport: DexScreenerTransport | None = None,
        coingecko_transport: CoinGeckoTransport | None = None,
        defillama_transport: DefiLlamaTransport | None = None,
        now: datetime | None = None,
    ) -> "LiveMarketLoader":
        registry = SourceRegistry()
        if dexscreener_transport is not None:
            registry.register(DexScreenerAdapter(dexscreener_transport, now=now))
        if coingecko_transport is not None:
            registry.register(CoinGeckoAdapter(coingecko_transport, now=now))
        if defillama_transport is not None:
            registry.register(DefiLlamaAdapter(defillama_transport, now=now))
        return cls(registry)
