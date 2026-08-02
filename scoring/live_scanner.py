"""Deterministic live research scanner with factor-level explanations.

This scanner produces research scores only. It never creates orders, paper fills,
leverage changes, cancellations, reversals or withdrawals.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import log
from statistics import median
from typing import Any

from data_pipeline.provider_contracts import (
    MarketDataBundle,
    ProviderHealthStatus,
    ReadOnlyMarketProvider,
    merge_provider_observations,
)
from intelligence.production_models import SignalDirection


FACTOR_WEIGHTS: Mapping[str, float] = {
    "price_structure": 20.0,
    "volume": 10.0,
    "order_book_imbalance": 10.0,
    "recent_trades": 10.0,
    "funding": 10.0,
    "oi_change": 10.0,
    "liquidation_pressure": 10.0,
    "btc_eth_correlation": 5.0,
    "news_catalyst": 5.0,
    "risk_reward": 10.0,
}

FACTOR_FIELD_NAMES: Mapping[str, str] = {
    "price_structure": "price_structure",
    "volume": "volume_score",
    "order_book_imbalance": "order_book_imbalance",
    "recent_trades": "trade_delta",
    "funding": "funding_signal",
    "oi_change": "oi_change_signal",
    "liquidation_pressure": "liquidation_signal",
    "btc_eth_correlation": "btc_eth_correlation",
    "news_catalyst": "news_catalyst",
    "risk_reward": "risk_reward_signal",
}


@dataclass(frozen=True)
class ScannerFactor:
    name: str
    weight: float
    raw_value: float
    normalized_value: float
    long_contribution: float
    short_contribution: float
    explanation: str
    source: str | None
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScannerScore:
    instrument_id: str
    status: str
    direction: SignalDirection
    score: float | None
    long_score: float | None
    short_score: float | None
    risk_score: float | None
    factors: tuple[ScannerFactor, ...]
    conflicts: tuple[str, ...]
    reason_codes: tuple[str, ...]
    observed_at: datetime | None
    can_execute_trades: bool = False

    def factor_breakdown(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "factor": factor.name,
                "weight": factor.weight,
                "raw_value": factor.raw_value,
                "normalized_value": factor.normalized_value,
                "long_contribution": factor.long_contribution,
                "short_contribution": factor.short_contribution,
                "explanation": factor.explanation,
                "source": factor.source,
                "reason_codes": list(factor.reason_codes),
                "can_execute_trades": False,
            }
            for factor in self.factors
        )


@dataclass(frozen=True)
class ScannerInput:
    instrument_id: str
    fields: Mapping[str, float]
    field_sources: Mapping[str, str] = None  # type: ignore[assignment]
    observed_at: datetime | None = None
    conflicts: tuple[str, ...] = ()
    critical_conflict: bool = False
    volume_reference: float | None = None


def score_scanner_input(
    scanner_input: ScannerInput,
    *,
    minimum_score: float = 62.0,
    minimum_edge: float = 7.0,
) -> ScannerScore:
    """Score complete evidence or fail closed with explicit missing-field reasons."""

    fields = dict(scanner_input.fields)
    sources = dict(scanner_input.field_sources or {})
    missing = tuple(
        name for name in FACTOR_WEIGHTS
        if FACTOR_FIELD_NAMES[name] not in fields
    )
    conflicts = tuple(scanner_input.conflicts)
    if missing:
        return ScannerScore(
            instrument_id=scanner_input.instrument_id,
            status="INSUFFICIENT_DATA",
            direction=SignalDirection.NO_TRADE,
            score=None,
            long_score=None,
            short_score=None,
            risk_score=None,
            factors=(),
            conflicts=conflicts,
            reason_codes=(
                "SCANNER_REQUIRED_FACTORS_MISSING",
                *(f"SCANNER_MISSING_{name.upper()}" for name in missing),
            ),
            observed_at=scanner_input.observed_at,
        )
    if scanner_input.critical_conflict:
        return ScannerScore(
            instrument_id=scanner_input.instrument_id,
            status="NO_TRADE",
            direction=SignalDirection.NO_TRADE,
            score=None,
            long_score=None,
            short_score=None,
            risk_score=None,
            factors=(),
            conflicts=conflicts,
            reason_codes=("SCANNER_CRITICAL_SOURCE_CONFLICT",),
            observed_at=scanner_input.observed_at,
        )

    factors: list[ScannerFactor] = []
    for name, weight in FACTOR_WEIGHTS.items():
        field_name = FACTOR_FIELD_NAMES[name]
        raw = float(fields[field_name])
        normalized = _clamp(raw)
        if name == "volume":
            normalized = _volume_signal(
                raw,
                reference=scanner_input.volume_reference,
                fields=fields,
            )
        elif name == "funding":
            normalized = _clamp(-raw / 0.003)
        elif name == "oi_change":
            normalized = _clamp(raw / 10.0)
        elif name == "liquidation_pressure":
            normalized = _clamp(-raw)
        elif name == "risk_reward":
            normalized = _clamp((raw - 1.0) / 3.0)
        long_contribution = weight * normalized / 2.0
        factors.append(
            ScannerFactor(
                name=name,
                weight=weight,
                raw_value=raw,
                normalized_value=normalized,
                long_contribution=long_contribution,
                short_contribution=-long_contribution,
                explanation=_explain_factor(name, raw, normalized),
                source=sources.get(field_name),
                reason_codes=(),
            )
        )

    directional_delta = sum(factor.long_contribution for factor in factors)
    long_score = _clamp(50.0 + directional_delta, 0.0, 100.0)
    short_score = _clamp(50.0 - directional_delta, 0.0, 100.0)
    best_score = max(long_score, short_score)
    edge = abs(long_score - short_score)
    direction = (
        SignalDirection.NO_TRADE
        if best_score < minimum_score or edge < minimum_edge
        else SignalDirection.LONG if long_score > short_score else SignalDirection.SHORT
    )
    status = "OK" if direction is not SignalDirection.NO_TRADE else "NO_TRADE"
    risk_score = _risk_score(fields, conflicts)
    reasons = ["SCANNER_FACTORS_COMPLETE", "RESEARCH_ONLY", "NO_EXECUTION_ACTION"]
    if conflicts:
        reasons.append("SOURCE_CONFLICT_WARNING")
        status = "DEGRADED"
        direction = SignalDirection.NO_TRADE
    return ScannerScore(
        instrument_id=scanner_input.instrument_id,
        status=status,
        direction=direction,
        score=best_score if direction is not SignalDirection.NO_TRADE else None,
        long_score=long_score,
        short_score=short_score,
        risk_score=risk_score,
        factors=tuple(factors),
        conflicts=conflicts,
        reason_codes=tuple(reasons),
        observed_at=scanner_input.observed_at,
    )


class LiveMarketScanner:
    """Combine registered read-only providers into explainable scanner scores."""

    def __init__(
        self,
        providers: Sequence[ReadOnlyMarketProvider],
        *,
        source_preference: Sequence[str] = (
            "bitunix_public",
            "coinglass",
            "coingecko",
            "coinmarketcap",
        ),
    ) -> None:
        self.providers = tuple(providers)
        self.source_preference = tuple(source_preference)

    async def scan(
        self,
        instrument_ids: Sequence[str],
        *,
        supplemental_fields: Mapping[str, Mapping[str, float]] | None = None,
        now: datetime | None = None,
    ) -> tuple[ScannerScore, ...]:
        reference = now or datetime.now(tz=UTC)
        instruments = tuple(dict.fromkeys(instrument_ids))
        all_results = await asyncio.gather(
            *(
                asyncio.gather(
                    *(provider.fetch(instrument_id, now=reference) for provider in self.providers)
                )
                for instrument_id in instruments
            )
        )
        bundles = tuple(
            merge_provider_observations(
                instrument_id,
                results,
                now=reference,
                source_preference=self.source_preference,
            )
            for instrument_id, results in zip(instruments, all_results, strict=True)
        )
        volumes = [
            bundle.fields["volume_24h_usd"]
            for bundle in bundles
            if bundle.fields.get("volume_24h_usd", 0.0) > 0
        ]
        volume_reference = median(volumes) if volumes else None
        scores: list[ScannerScore] = []
        for bundle in bundles:
            fields = dict(bundle.fields)
            fields.update((supplemental_fields or {}).get(bundle.instrument_id, {}))
            scores.append(
                score_scanner_input(
                    ScannerInput(
                        instrument_id=bundle.instrument_id,
                        fields=fields,
                        field_sources=bundle.field_sources,
                        observed_at=bundle.observed_at,
                        conflicts=tuple(conflict.field for conflict in bundle.conflicts),
                        critical_conflict=bundle.has_critical_conflict,
                        volume_reference=volume_reference,
                    )
                )
            )
        return tuple(scores)


def _volume_signal(
    raw: float,
    *,
    reference: float | None,
    fields: Mapping[str, float],
) -> float:
    if "volume_score" in fields:
        return _clamp(raw)
    if raw <= 0 or reference is None or reference <= 0:
        return 0.0
    return _clamp(log(raw / reference) / 2.0)


def _risk_score(fields: Mapping[str, float], conflicts: Sequence[str]) -> float:
    risk = 25.0
    risk += abs(float(fields.get("spread_bps", 0.0))) / 2.0
    risk += abs(float(fields.get("funding_rate", 0.0))) * 5_000.0
    risk += abs(float(fields.get("liquidation_pressure", 0.0))) * 20.0
    risk += 20.0 if conflicts else 0.0
    return _clamp(risk)


def _explain_factor(name: str, raw: float, normalized: float) -> str:
    if name == "funding":
        return "Positive funding penalizes long crowding; negative funding supports a long contrarian reading."
    if name == "liquidation_pressure":
        return "Positive raw pressure means more long liquidations, which is bearish for a long setup."
    if name == "oi_change":
        return "Open-interest expansion confirms participation; contraction weakens conviction."
    if name == "risk_reward":
        return "Risk/reward is normalized above 1:1 and capped to prevent oversized influence."
    if normalized > 0.2:
        return f"{name} contributes bullish evidence ({raw:.4f})."
    if normalized < -0.2:
        return f"{name} contributes bearish evidence ({raw:.4f})."
    return f"{name} is neutral or inconclusive ({raw:.4f})."


def _clamp(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))
