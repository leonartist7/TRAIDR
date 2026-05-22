"""Fail-closed normalized market snapshot validation."""

from __future__ import annotations

from datetime import timedelta

from data_pipeline.contracts import DataQuality, NormalizedMarketSnapshot
from utils.clocks import check_freshness
from utils.results import Result

DEFAULT_MARKET_MAX_AGE = timedelta(minutes=5)


def validate_snapshot(
    snapshot: NormalizedMarketSnapshot | None,
    *,
    now=None,
    max_age: timedelta = DEFAULT_MARKET_MAX_AGE,
) -> Result[NormalizedMarketSnapshot]:
    if snapshot is None:
        return Result.insufficient_data("MARKET_SOURCE_MISSING")
    if snapshot.freshness.quality is not DataQuality.SUFFICIENT:
        return Result.insufficient_data(f"MARKET_{snapshot.freshness.quality.value.upper()}")
    if not snapshot.provenance.source_name or not snapshot.provenance.source_record_id:
        return Result.insufficient_data("MARKET_PROVENANCE_MISSING")
    if snapshot.identity.base_symbol == snapshot.identity.quote_symbol:
        return Result.insufficient_data("MARKET_IDENTITY_CONTRADICTORY")
    if snapshot.metrics.price_usd <= 0 or snapshot.metrics.liquidity_usd < 0:
        return Result.insufficient_data("MARKET_METRICS_MALFORMED")
    if snapshot.metrics.volume_24h_usd < 0:
        return Result.insufficient_data("MARKET_METRICS_CONTRADICTORY")

    freshness = check_freshness(snapshot.freshness.observed_at, max_age=max_age, now=now)
    if not freshness.ok:
        return Result.insufficient_data(*freshness.reason_codes)
    return Result.success(snapshot)

