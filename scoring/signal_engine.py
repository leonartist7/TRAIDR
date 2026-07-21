"""Explainable LONG/SHORT/NO_TRADE decisions under deterministic veto authority."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from hashlib import sha256

from intelligence.production_models import FeatureSnapshot, SignalDecision, SignalDirection
from scoring.calibration import ProbabilityEvidence, gate_probability

SIGNAL_MODEL_VERSION = "deterministic-directional-v1"


def score_directional_setup(
    snapshot: FeatureSnapshot,
    *,
    probability_evidence: ProbabilityEvidence | None = None,
    token_safety_required: bool = False,
    token_safety_clear: bool | None = None,
) -> SignalDecision:
    features = snapshot.features
    vetoes: list[str] = list(snapshot.contradiction_flags)
    if snapshot.data_coverage < 0.75:
        vetoes.append("DATA_COVERAGE_INSUFFICIENT")
    if "EXTREME_SPREAD" in snapshot.quality_warnings:
        vetoes.append("EXTREME_SPREAD")
    if token_safety_required and token_safety_clear is not True:
        vetoes.append("TOKEN_SAFETY_NOT_VERIFIED")
    required = ("last_price", "trend_strength_pct", "rsi_14", "atr_pct", "breakout_position")
    if any(name not in features for name in required):
        vetoes.append("REQUIRED_FEATURES_MISSING")

    trend = features.get("trend_strength_pct", 0.0)
    rsi = features.get("rsi_14", 50.0)
    breakout = features.get("breakout_position", 0.5)
    volume_z = features.get("volume_zscore", 0.0)
    return_5 = features.get("return_5", 0.0)
    depth = features.get("depth_imbalance", 0.0)
    funding = features.get("funding_rate", 0.0)
    basis = features.get("basis_bps", 0.0)
    spread = max(0.0, features.get("spread_bps", 0.0))

    long_score = 50.0
    long_score += _clamp(trend * 8.0, -20.0, 20.0)
    long_score += _clamp((breakout - 0.5) * 30.0, -15.0, 15.0)
    long_score += _clamp((rsi - 50.0) * 0.35, -10.0, 10.0)
    long_score += _clamp(volume_z * 2.5, -6.0, 6.0)
    long_score += _clamp(return_5 * 1.2, -8.0, 8.0)
    long_score += _clamp(depth * 10.0, -8.0, 8.0)
    long_score -= _clamp(funding * 10_000.0, -5.0, 8.0)
    long_score -= _clamp(max(basis, 0.0) / 8.0, 0.0, 5.0)

    short_score = 50.0
    short_score -= _clamp(trend * 8.0, -20.0, 20.0)
    short_score -= _clamp((breakout - 0.5) * 30.0, -15.0, 15.0)
    short_score -= _clamp((rsi - 50.0) * 0.35, -10.0, 10.0)
    short_score += _clamp(volume_z * 2.0, -5.0, 5.0)
    short_score -= _clamp(return_5 * 1.2, -8.0, 8.0)
    short_score -= _clamp(depth * 10.0, -8.0, 8.0)
    short_score += _clamp(funding * 10_000.0, -5.0, 8.0)
    short_score += _clamp(max(basis, 0.0) / 8.0, 0.0, 5.0)

    long_score = _clamp(long_score, 0.0, 100.0)
    short_score = _clamp(short_score, 0.0, 100.0)
    best_score = max(long_score, short_score)
    edge = abs(long_score - short_score)
    if vetoes or best_score < 62.0 or edge < 7.0:
        direction = SignalDirection.NO_TRADE
    else:
        direction = SignalDirection.LONG if long_score > short_score else SignalDirection.SHORT

    volatility = features.get("realized_volatility_pct", 0.0)
    risk_score = _clamp(
        18.0 + volatility * 3.0 + spread / 4.0 + abs(funding) * 8_000.0 + abs(basis) / 10.0,
        0.0,
        100.0,
    )
    probability = gate_probability(
        probability_evidence,
        data_coverage=snapshot.data_coverage,
        has_veto=bool(vetoes),
    )
    probability_state, success_probability, probability_low, probability_high, sample_size, probability_model = probability

    generated_at = snapshot.calculated_at
    expires_at = generated_at + timedelta(seconds=_horizon_seconds(snapshot.horizon))
    price = Decimal(str(features.get("last_price", 0.0)))
    atr_fraction = max(features.get("atr_pct", 0.0) / 100.0, 0.004)
    stop_distance = price * Decimal(str(atr_fraction * 1.4))
    target_distance = stop_distance * Decimal("2")
    entry_low: Decimal | None = None
    entry_high: Decimal | None = None
    stop: Decimal | None = None
    invalidation: Decimal | None = None
    targets: tuple[Decimal, ...] = ()
    risk_reward: float | None = None
    expected_return: float | None = None
    if direction is not SignalDirection.NO_TRADE and price > 0:
        entry_padding = price * Decimal("0.0015")
        entry_low, entry_high = price - entry_padding, price + entry_padding
        if direction is SignalDirection.LONG:
            stop = price - stop_distance
            targets = (price + target_distance, price + target_distance * Decimal("1.5"))
        else:
            stop = price + stop_distance
            targets = (price - target_distance, price - target_distance * Decimal("1.5"))
        invalidation = stop
        risk_reward = 2.0
        gross_return = float(target_distance / price * Decimal("100"))
        expected_return = gross_return - (spread / 100.0) - 0.12

    reasons = _reasons(snapshot, direction, long_score, short_score, vetoes)
    digest = sha256(
        f"{snapshot.feature_id}|{direction.value}|{SIGNAL_MODEL_VERSION}".encode("utf-8")
    ).hexdigest()[:24]
    return SignalDecision(
        signal_id=f"signal-{digest}",
        idempotency_key=f"signal:{digest}",
        instrument_id=snapshot.instrument_id,
        direction=direction,
        horizon=snapshot.horizon,
        setup_type=_setup_type(snapshot.regime, direction),
        generated_at=generated_at,
        expires_at=expires_at,
        entry_low=entry_low,
        entry_high=entry_high,
        invalidation=invalidation,
        stop=stop,
        targets=targets,
        expected_return_pct=expected_return,
        risk_reward=risk_reward,
        opportunity_score=round(best_score, 4),
        risk_score=round(risk_score, 4),
        data_coverage=snapshot.data_coverage,
        probability_state=probability_state,
        success_probability=success_probability,
        probability_low=probability_low,
        probability_high=probability_high,
        calibration_sample_size=sample_size,
        model_version=f"{SIGNAL_MODEL_VERSION}+{probability_model}",
        liquidity_grade=_liquidity_grade(spread),
        risk_grade=_risk_grade(risk_score),
        reasons=tuple(reasons),
        hard_vetoes=tuple(dict.fromkeys(vetoes)),
        evidence_ids=snapshot.evidence_ids,
    )


def _reasons(
    snapshot: FeatureSnapshot,
    direction: SignalDirection,
    long_score: float,
    short_score: float,
    vetoes: list[str],
) -> list[str]:
    if vetoes:
        return ["Deterministic safety or data-quality veto requires NO_TRADE.", *vetoes]
    if direction is SignalDirection.NO_TRADE:
        return [
            "Directional evidence is not sufficiently strong or separated.",
            f"Long score {long_score:.1f}; short score {short_score:.1f}.",
        ]
    return [
        f"{direction.value} evidence leads by {abs(long_score - short_score):.1f} points.",
        f"Market regime is {snapshot.regime}.",
        f"Evidence coverage is {snapshot.data_coverage:.0%}.",
    ]


def _setup_type(regime: str, direction: SignalDirection) -> str:
    if direction is SignalDirection.NO_TRADE:
        return "NO_VALID_SETUP"
    if regime == "COMPRESSION":
        return "COMPRESSION_BREAKOUT"
    if regime.startswith("TREND"):
        return "TREND_CONTINUATION"
    return "RANGE_REVERSAL_OR_BREAKOUT"


def _liquidity_grade(spread_bps: float) -> str:
    if spread_bps <= 5:
        return "A"
    if spread_bps <= 15:
        return "B"
    if spread_bps <= 35:
        return "C"
    return "D"


def _risk_grade(score: float) -> str:
    if score < 30:
        return "LOW"
    if score < 55:
        return "MODERATE"
    if score < 75:
        return "HIGH"
    return "EXTREME"


def _horizon_seconds(horizon: str) -> int:
    return {"5m": 300, "15m": 900, "1h": 3600, "4h": 14_400, "1d": 86_400}[horizon]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
