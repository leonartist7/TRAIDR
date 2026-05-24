"""Deterministic macro regime scoring for local research."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MacroRegimeScore:
    classification: str
    score: float
    confidence: float
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "score": self.score,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": False,
        }


def score_macro_regime(signals: Mapping[str, Any]) -> MacroRegimeScore:
    values = [_normalized(value) for value in signals.values()]
    usable = [value for value in values if value is not None]
    if not usable:
        return MacroRegimeScore("INSUFFICIENT_DATA", 0.0, 0.0, ("MACRO_SIGNALS_MISSING",))

    score = sum(usable) / len(usable)
    confidence = min(1.0, len(usable) / max(len(values), 3))
    reasons: list[str] = []
    if len(usable) < len(values):
        reasons.append("MACRO_SIGNAL_PARTIAL")
        confidence = max(0.0, confidence - 0.15)
    if score >= 0.6:
        classification = "RISK_ON"
        reasons.append("MACRO_RISK_ON")
    elif score <= 0.4:
        classification = "RISK_OFF"
        reasons.append("MACRO_RISK_OFF")
    else:
        classification = "NEUTRAL"
        reasons.append("MACRO_NEUTRAL")
    return MacroRegimeScore(classification, round(score, 4), round(confidence, 4), tuple(reasons))


def combine_macro_regimes(regimes: Sequence[MacroRegimeScore]) -> MacroRegimeScore:
    usable = [regime for regime in regimes if regime.classification != "INSUFFICIENT_DATA"]
    if not usable:
        return MacroRegimeScore("INSUFFICIENT_DATA", 0.0, 0.0, ("MACRO_REGIMES_MISSING",))
    return score_macro_regime({f"regime_{index}": regime.score for index, regime in enumerate(usable)})


def _normalized(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return min(1.0, max(0.0, float(value)))

