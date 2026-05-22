"""Fixture/raw market record normalization into internal snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from data_pipeline.contracts import (
    AdapterResult,
    DataProvenance,
    DataQuality,
    FreshnessFields,
    MarketIdentity,
    MarketMetrics,
    NormalizedMarketSnapshot,
)
from data_pipeline.validation import validate_snapshot
from utils.clocks import parse_utc_timestamp

_REQUIRED_FIELDS = (
    "pair_id",
    "chain_id",
    "base_symbol",
    "quote_symbol",
    "price_usd",
    "liquidity_usd",
    "volume_24h_usd",
    "observed_at",
    "source_record_id",
)


def normalize_market_record(
    raw: Mapping[str, Any] | None,
    *,
    source_name: str,
    retrieved_at: datetime | str | None = None,
    now: datetime | str | None = None,
) -> AdapterResult[NormalizedMarketSnapshot]:
    if raw is None:
        return AdapterResult.insufficient("MARKET_SOURCE_MISSING")
    if any(field not in raw or raw[field] is None for field in _REQUIRED_FIELDS):
        return AdapterResult.insufficient("MARKET_SOURCE_FIELDS_MISSING")

    observed = parse_utc_timestamp(raw["observed_at"])
    retrieved = parse_utc_timestamp(retrieved_at or raw.get("retrieved_at") or datetime.now(timezone.utc))
    normalized_at = parse_utc_timestamp(now or retrieved.value)
    if not observed.ok or observed.value is None:
        return AdapterResult.insufficient(*observed.reason_codes)
    if not retrieved.ok or retrieved.value is None or not normalized_at.ok or normalized_at.value is None:
        return AdapterResult.insufficient("MARKET_RETRIEVAL_TIME_INVALID")

    try:
        snapshot = NormalizedMarketSnapshot(
            identity=MarketIdentity(
                pair_id=_text(raw["pair_id"]),
                chain_id=_text(raw["chain_id"]),
                base_symbol=_text(raw["base_symbol"]),
                quote_symbol=_text(raw["quote_symbol"]),
            ),
            metrics=MarketMetrics(
                price_usd=_decimal(raw["price_usd"]),
                liquidity_usd=_decimal(raw["liquidity_usd"]),
                volume_24h_usd=_decimal(raw["volume_24h_usd"]),
            ),
            provenance=DataProvenance(
                source_name=source_name,
                source_record_id=_text(raw["source_record_id"]),
                retrieved_at=retrieved.value,
                raw_status=_text(raw.get("raw_status", "fixture")),
            ),
            freshness=FreshnessFields(
                observed_at=observed.value,
                normalized_at=normalized_at.value,
                quality=_quality(raw.get("quality", DataQuality.SUFFICIENT.value)),
            ),
        )
    except (InvalidOperation, TypeError, ValueError):
        return AdapterResult.insufficient("MARKET_RECORD_MALFORMED")

    validated = validate_snapshot(snapshot, now=now or normalized_at.value)
    if not validated.ok or validated.value is None:
        return AdapterResult.insufficient(*validated.reason_codes)
    return AdapterResult.success(validated.value)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _text(value: Any) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("normalized market text fields cannot be empty")
    return text


def _quality(value: Any) -> DataQuality:
    return DataQuality(str(value).lower())

