"""Safe optional source registry for fixture-first adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from data_pipeline.contracts import AdapterResult, NormalizedMarketSnapshot


class MarketSource(Protocol):
    name: str

    def fetch_snapshot(self, pair_ref: str) -> AdapterResult[NormalizedMarketSnapshot]:
        ...


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, MarketSource] = {}

    def register(self, source: MarketSource) -> None:
        self._sources[source.name] = source

    def fetch(self, source_name: str, pair_ref: str) -> AdapterResult[NormalizedMarketSnapshot]:
        source = self._sources.get(source_name)
        if source is None:
            return AdapterResult.insufficient("SOURCE_UNAVAILABLE")
        return source.fetch_snapshot(pair_ref)

    @classmethod
    def from_factories(cls, *factories: Callable[[], MarketSource]) -> "SourceRegistry":
        registry = cls()
        for factory in factories:
            registry.register(factory())
        return registry

