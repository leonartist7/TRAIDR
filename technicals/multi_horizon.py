"""Deterministic multi-horizon market features with explicit coverage and freshness."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from math import sqrt
from statistics import fmean, pstdev
from typing import Literal, Sequence

from data_pipeline.bitunix_models import BITUNIX_INTERVAL_SECONDS, BitunixCandle
from intelligence.production_models import FeatureSnapshot
from utils.results import Result

Horizon = Literal["5m", "15m", "1h", "4h", "1d"]
FEATURE_VERSION = "multi-horizon-v1"
_BASE_FEATURE_COUNT = 13
_TOTAL_FEATURE_COUNT = 19


def build_multi_horizon_features(
    *,
    instrument_id: str,
    horizon: Horizon,
    candles: Sequence[BitunixCandle],
    evidence_ids: Sequence[str],
    depth_imbalance: float | None = None,
    spread_bps: float | None = None,
    funding_rate: float | None = None,
    basis_bps: float | None = None,
    trade_delta: float | None = None,
    cross_market_divergence_bps: float | None = None,
    now: datetime | None = None,
) -> Result[FeatureSnapshot]:
    """Calculate explainable features or fail closed when history is unsafe."""

    reference = now or datetime.now(tz=UTC)
    if not instrument_id.strip() or not evidence_ids:
        return Result.insufficient_data("FEATURE_IDENTITY_OR_EVIDENCE_MISSING")
    if horizon not in BITUNIX_INTERVAL_SECONDS:
        return Result.insufficient_data("FEATURE_HORIZON_UNSUPPORTED")
    if len(candles) < 30:
        return Result.insufficient_data("FEATURE_LOOKBACK_INSUFFICIENT")
    prepared = sorted(candles, key=lambda item: item.time_ms)
    if len({item.time_ms for item in prepared}) != len(prepared):
        return Result.insufficient_data("FEATURE_DUPLICATE_CANDLES")
    latest_at = prepared[-1].observed_at
    if (reference - latest_at).total_seconds() > BITUNIX_INTERVAL_SECONDS[horizon] * 2:
        return Result.insufficient_data("FEATURE_CANDLES_STALE")

    closes = [float(item.close) for item in prepared]
    highs = [float(item.high) for item in prepared]
    lows = [float(item.low) for item in prepared]
    volumes = [float(item.base_volume) for item in prepared]
    returns = [(closes[index] / closes[index - 1]) - 1.0 for index in range(1, len(closes))]
    ranges = [
        max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )
        for index in range(1, len(closes))
    ]
    sma_fast = fmean(closes[-10:])
    sma_slow = fmean(closes[-30:])
    atr = fmean(ranges[-14:])
    recent_high = max(highs[-20:])
    recent_low = min(lows[-20:])
    range_span = max(recent_high - recent_low, closes[-1] * 1e-9)
    volume_mean = fmean(volumes[-20:])
    volume_deviation = pstdev(volumes[-20:])
    realized_volatility = pstdev(returns[-20:]) * sqrt(20) * 100 if len(returns) >= 2 else 0.0
    recent_atr = fmean(ranges[-5:])
    prior_atr = fmean(ranges[-20:-5]) if ranges[-20:-5] else atr

    features: dict[str, float] = {
        "last_price": closes[-1],
        "return_1": returns[-1] * 100,
        "return_5": ((closes[-1] / closes[-6]) - 1.0) * 100,
        "sma_fast": sma_fast,
        "sma_slow": sma_slow,
        "trend_strength_pct": ((sma_fast / sma_slow) - 1.0) * 100,
        "rsi_14": _rsi(closes, 14),
        "atr_pct": atr / closes[-1] * 100,
        "realized_volatility_pct": realized_volatility,
        "volume_zscore": (volumes[-1] - volume_mean) / volume_deviation if volume_deviation else 0.0,
        "breakout_position": (closes[-1] - recent_low) / range_span,
        "range_compression": recent_atr / prior_atr if prior_atr else 1.0,
        "fair_value_gap_count": float(_fair_value_gap_count(prepared[-40:])),
        "support": recent_low,
        "resistance": recent_high,
    }
    optional = {
        "depth_imbalance": depth_imbalance,
        "spread_bps": spread_bps,
        "funding_rate": funding_rate,
        "basis_bps": basis_bps,
        "trade_delta": trade_delta,
        "cross_market_divergence_bps": cross_market_divergence_bps,
    }
    missing: list[str] = []
    for name, value in optional.items():
        if value is None:
            missing.append(name)
        else:
            features[name] = float(value)

    regime = _market_regime(features)
    warnings: list[str] = []
    if abs(features.get("spread_bps", 0.0)) > 50:
        warnings.append("EXTREME_SPREAD")
    if features["realized_volatility_pct"] > 12:
        warnings.append("HIGH_REALIZED_VOLATILITY")
    coverage = min(1.0, (_BASE_FEATURE_COUNT + len(optional) - len(missing)) / _TOTAL_FEATURE_COUNT)
    fingerprint = sha256(
        f"{instrument_id}|{horizon}|{prepared[-1].time_ms}|{FEATURE_VERSION}".encode("utf-8")
    ).hexdigest()[:24]
    snapshot = FeatureSnapshot(
        feature_id=f"feature-{fingerprint}",
        instrument_id=instrument_id,
        horizon=horizon,
        observed_at=latest_at,
        calculated_at=reference,
        feature_version=FEATURE_VERSION,
        regime=regime,
        features={key: round(value, 10) for key, value in features.items()},
        data_coverage=coverage,
        missing_features=tuple(missing),
        quality_warnings=tuple(warnings),
        contradiction_flags=(),
        evidence_ids=tuple(dict.fromkeys(evidence_ids)),
    )
    return Result.success(snapshot)


def _rsi(closes: Sequence[float], period: int) -> float:
    changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))][-period:]
    gains = fmean([max(change, 0.0) for change in changes])
    losses = fmean([max(-change, 0.0) for change in changes])
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    relative_strength = gains / losses
    return 100.0 - (100.0 / (1.0 + relative_strength))


def _fair_value_gap_count(candles: Sequence[BitunixCandle]) -> int:
    count = 0
    for index in range(2, len(candles)):
        if candles[index].low > candles[index - 2].high:
            count += 1
        elif candles[index].high < candles[index - 2].low:
            count += 1
    return count


def _market_regime(features: dict[str, float]) -> str:
    trend = features["trend_strength_pct"]
    volatility = features["realized_volatility_pct"]
    if volatility > 12:
        return "VOLATILE"
    if trend > 0.35 and features["breakout_position"] > 0.58:
        return "TREND_UP"
    if trend < -0.35 and features["breakout_position"] < 0.42:
        return "TREND_DOWN"
    if features["range_compression"] < 0.72:
        return "COMPRESSION"
    return "RANGE"
