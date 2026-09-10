"""Zero-weight derivatives classifications for research and future ablation.

Shadow assessments are descriptive evidence. They cannot alter production scanner
scores, approve paper risk, or create an execution action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Mapping

from intelligence.production_models import SignalDirection


class SetupClass(StrEnum):
    MOMENTUM_BUILD = "MOMENTUM_BUILD"
    SHORT_BUILD = "SHORT_BUILD"
    SHORT_SQUEEZE = "SHORT_SQUEEZE"
    LONG_LIQUIDATION = "LONG_LIQUIDATION"
    BALANCED = "BALANCED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class MarketRegime(StrEnum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    DERIVATIVES_STRESS = "DERIVATIVES_STRESS"
    NEUTRAL = "NEUTRAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ProbabilityState(StrEnum):
    UNCALIBRATED = "UNCALIBRATED"
    CALIBRATED = "CALIBRATED"


SHADOW_REQUIRED_FIELDS = (
    "price_change_1h_pct",
    "oi_change_pct_1h",
    "funding_rate",
    "liquidation_pressure",
    "taker_buy_sell_imbalance",
)


@dataclass(frozen=True)
class ShadowStrategyAssessment:
    instrument_id: str
    observed_at: datetime | None
    assessed_at: datetime
    status: str
    decision: SignalDirection
    setup_class: SetupClass
    market_regime: MarketRegime
    crowding_score: float | None
    squeeze_risk: float | None
    catalyst_risk: float | None
    data_quality_score: float
    probability_state: ProbabilityState
    probability: float | None
    scoring_weight: float
    conflicts: tuple[str, ...]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "assessed_at": self.assessed_at.isoformat(),
            "status": self.status,
            "decision": self.decision.value,
            "setup_class": self.setup_class.value,
            "market_regime": self.market_regime.value,
            "crowding_score": self.crowding_score,
            "squeeze_risk": self.squeeze_risk,
            "catalyst_risk": self.catalyst_risk,
            "data_quality_score": self.data_quality_score,
            "probability_state": self.probability_state.value,
            "probability": self.probability,
            "scoring_weight": self.scoring_weight,
            "conflicts": list(self.conflicts),
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


def classify_shadow_strategy(
    instrument_id: str,
    fields: Mapping[str, float],
    *,
    observed_at: datetime | None,
    reference_at: datetime | None = None,
    conflicts: tuple[str, ...] = (),
    maximum_age: timedelta = timedelta(minutes=5),
) -> ShadowStrategyAssessment:
    """Classify derivatives behavior while forcing zero weight and NO_TRADE."""

    now = reference_at or datetime.now(tz=UTC)
    available = sum(1 for field in SHADOW_REQUIRED_FIELDS if field in fields)
    quality = available / len(SHADOW_REQUIRED_FIELDS) * 100.0
    reasons = ["SHADOW_ONLY", "ZERO_SCORING_WEIGHT", "UNCALIBRATED_PROBABILITY"]
    stale = observed_at is None or observed_at > now or now - observed_at > maximum_age
    missing = tuple(field for field in SHADOW_REQUIRED_FIELDS if field not in fields)
    if stale:
        reasons.append("SHADOW_EVIDENCE_STALE")
        quality = min(quality, 25.0)
    if missing:
        reasons.extend(f"SHADOW_MISSING_{field.upper()}" for field in missing)
    if conflicts:
        reasons.append("SHADOW_SOURCE_CONFLICT")
        quality = min(quality, 50.0)

    if stale or missing or conflicts:
        return ShadowStrategyAssessment(
            instrument_id=instrument_id,
            observed_at=observed_at,
            assessed_at=now,
            status="INSUFFICIENT_DATA" if stale or missing else "DEGRADED",
            decision=SignalDirection.NO_TRADE,
            setup_class=SetupClass.INSUFFICIENT_DATA,
            market_regime=MarketRegime.INSUFFICIENT_DATA,
            crowding_score=_crowding_score(fields),
            squeeze_risk=_squeeze_risk(fields),
            catalyst_risk=_catalyst_risk(fields),
            data_quality_score=round(quality, 2),
            probability_state=ProbabilityState.UNCALIBRATED,
            probability=None,
            scoring_weight=0.0,
            conflicts=conflicts,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )

    price_change = float(fields["price_change_1h_pct"])
    oi_change = float(fields["oi_change_pct_1h"])
    taker_flow = float(fields["taker_buy_sell_imbalance"])
    liquidation_pressure = float(fields["liquidation_pressure"])
    crowding = _crowding_score(fields)
    squeeze = _squeeze_risk(fields)
    catalyst = _catalyst_risk(fields)

    if price_change > 0 and oi_change > 0:
        setup = SetupClass.MOMENTUM_BUILD
    elif price_change > 0 and oi_change < 0:
        setup = SetupClass.SHORT_SQUEEZE
        reasons.append("CHASE_RISK")
    elif price_change < 0 and oi_change > 0:
        setup = SetupClass.SHORT_BUILD
    elif price_change < 0 and oi_change < 0:
        setup = SetupClass.LONG_LIQUIDATION
        reasons.append("WAIT_FOR_STABILIZATION")
    else:
        setup = SetupClass.BALANCED

    if abs(liquidation_pressure) >= 0.65 or (crowding or 0.0) >= 75.0:
        regime = MarketRegime.DERIVATIVES_STRESS
    elif price_change > 0 and taker_flow > 0:
        regime = MarketRegime.RISK_ON
    elif price_change < 0 and taker_flow < 0:
        regime = MarketRegime.RISK_OFF
    else:
        regime = MarketRegime.NEUTRAL

    return ShadowStrategyAssessment(
        instrument_id=instrument_id,
        observed_at=observed_at,
        assessed_at=now,
        status="SHADOW",
        decision=SignalDirection.NO_TRADE,
        setup_class=setup,
        market_regime=regime,
        crowding_score=crowding,
        squeeze_risk=squeeze,
        catalyst_risk=catalyst,
        data_quality_score=100.0,
        probability_state=ProbabilityState.UNCALIBRATED,
        probability=None,
        scoring_weight=0.0,
        conflicts=(),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def _crowding_score(fields: Mapping[str, float]) -> float | None:
    components: list[float] = []
    if "funding_rate" in fields:
        components.append(min(25.0, abs(float(fields["funding_rate"])) / 0.003 * 25.0))
    if "long_short_ratio" in fields:
        components.append(min(25.0, abs(float(fields["long_short_ratio"]) - 1.0) / 0.5 * 25.0))
    if "oi_market_cap_ratio" in fields:
        components.append(min(25.0, max(0.0, float(fields["oi_market_cap_ratio"])) / 0.05 * 25.0))
    if "oi_volume_ratio" in fields:
        components.append(min(25.0, max(0.0, float(fields["oi_volume_ratio"])) * 25.0))
    return round(sum(components), 2) if components else None


def _squeeze_risk(fields: Mapping[str, float]) -> float | None:
    components: list[float] = []
    if "liquidation_pressure" in fields:
        components.append(min(45.0, abs(float(fields["liquidation_pressure"])) * 45.0))
    if "liquidation_acceleration_pct" in fields:
        components.append(min(30.0, max(0.0, float(fields["liquidation_acceleration_pct"])) / 100.0 * 30.0))
    if "oi_change_pct_1h" in fields and "price_change_1h_pct" in fields:
        if float(fields["oi_change_pct_1h"]) < 0 and abs(float(fields["price_change_1h_pct"])) > 0:
            components.append(min(25.0, abs(float(fields["price_change_1h_pct"])) / 5.0 * 25.0))
    return round(sum(components), 2) if components else None


def _catalyst_risk(fields: Mapping[str, float]) -> float | None:
    names = ("news_importance", "news_novelty", "news_corroboration")
    if not any(name in fields for name in names):
        return None
    importance = max(0.0, min(1.0, float(fields.get("news_importance", 0.0))))
    novelty = max(0.0, min(1.0, float(fields.get("news_novelty", 0.0))))
    corroboration = max(0.0, min(1.0, float(fields.get("news_corroboration", 0.0))))
    return round((importance * 0.5 + novelty * 0.25 + corroboration * 0.25) * 100.0, 2)
