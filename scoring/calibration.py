"""Probability calibration utilities with strict display eligibility gates."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt
from typing import Sequence

from intelligence.production_models import ProbabilityState


@dataclass(frozen=True)
class ProbabilityEvidence:
    calibrated_probability: float
    sample_size: int
    expected_calibration_error: float
    model_version: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.calibrated_probability <= 1.0:
            raise ValueError("calibrated probability must be between zero and one")
        if self.sample_size < 0 or self.expected_calibration_error < 0:
            raise ValueError("calibration evidence cannot be negative")


def gate_probability(
    evidence: ProbabilityEvidence | None,
    *,
    data_coverage: float,
    has_veto: bool,
) -> tuple[ProbabilityState, float | None, float | None, float | None, int, str]:
    if has_veto:
        return ProbabilityState.BLOCKED, None, None, None, 0, "deterministic-veto"
    if evidence is None:
        return ProbabilityState.UNCALIBRATED, None, None, None, 0, "baseline-v1"
    if evidence.sample_size < 500 or evidence.expected_calibration_error > 0.05 or data_coverage < 0.75:
        return (
            ProbabilityState.UNCALIBRATED,
            None,
            None,
            None,
            evidence.sample_size,
            evidence.model_version,
        )
    probability = evidence.calibrated_probability
    error = 1.96 * sqrt(max(probability * (1.0 - probability), 1e-9) / evidence.sample_size)
    return (
        ProbabilityState.CALIBRATED,
        probability,
        max(0.0, probability - error),
        min(1.0, probability + error),
        evidence.sample_size,
        evidence.model_version,
    )


def expected_calibration_error(
    probabilities: Sequence[float],
    outcomes: Sequence[int | bool],
    *,
    bins: int = 10,
) -> float:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes require equal non-empty lengths")
    if bins < 2:
        raise ValueError("calibration requires at least two bins")
    total = len(probabilities)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = [
            position
            for position, probability in enumerate(probabilities)
            if lower <= probability <= upper and (index == bins - 1 or probability < upper)
        ]
        if not members:
            continue
        confidence = sum(probabilities[position] for position in members) / len(members)
        accuracy = sum(int(bool(outcomes[position])) for position in members) / len(members)
        error += len(members) / total * abs(confidence - accuracy)
    return error


def fit_sigmoid_calibrator(
    raw_scores: Sequence[float],
    outcomes: Sequence[int | bool],
    *,
    iterations: int = 1500,
    learning_rate: float = 0.05,
) -> tuple[float, float]:
    """Fit a tiny deterministic Platt-style sigmoid without external model authority."""

    if len(raw_scores) != len(outcomes) or len(raw_scores) < 20:
        raise ValueError("sigmoid calibration requires at least twenty labeled scores")
    normalized = [max(0.0, min(1.0, score / 100.0)) for score in raw_scores]
    labels = [1.0 if bool(value) else 0.0 for value in outcomes]
    slope = 1.0
    intercept = 0.0
    for _ in range(iterations):
        grad_slope = 0.0
        grad_intercept = 0.0
        for score, label in zip(normalized, labels, strict=True):
            predicted = _sigmoid(slope * score + intercept)
            difference = predicted - label
            grad_slope += difference * score
            grad_intercept += difference
        scale = 1.0 / len(labels)
        slope -= learning_rate * grad_slope * scale
        intercept -= learning_rate * grad_intercept * scale
    return slope, intercept


def apply_sigmoid(raw_score: float, slope: float, intercept: float) -> float:
    return _sigmoid(slope * max(0.0, min(1.0, raw_score / 100.0)) + intercept)


def _sigmoid(value: float) -> float:
    if value >= 0:
        inverse = exp(-value)
        return 1.0 / (1.0 + inverse)
    direct = exp(value)
    return direct / (1.0 + direct)
