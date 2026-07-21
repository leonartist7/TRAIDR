"""Local champion/challenger training with chronological holdout evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean, pstdev
from typing import Mapping, Sequence

from scoring.calibration import apply_sigmoid, expected_calibration_error, fit_sigmoid_calibrator
from utils.results import Result


@dataclass(frozen=True)
class TrainedModelReport:
    champion_kind: str
    feature_names: tuple[str, ...]
    training_start: datetime
    training_end: datetime
    training_samples: int
    validation_samples: int
    test_samples: int
    baseline_brier: float
    challenger_brier: float
    champion_brier: float
    champion_ece: float
    net_return_after_costs: float
    maximum_drawdown: float
    regime_stability: float
    promoted: bool
    reason_codes: tuple[str, ...]
    model: object


def train_champion_challenger(
    rows: Sequence[Mapping[str, float]],
    outcomes: Sequence[int | bool],
    observed_at: Sequence[datetime],
    *,
    net_returns: Sequence[float] | None = None,
    regimes: Sequence[str] | None = None,
    current_champion_metrics: Mapping[str, float] | None = None,
) -> Result[TrainedModelReport]:
    """Train interpretable logistic and nonlinear HGB candidates using time splits."""

    if not (len(rows) == len(outcomes) == len(observed_at)) or len(rows) < 500:
        return Result.insufficient_data("MODEL_MINIMUM_500_LABELS_REQUIRED")
    if net_returns is not None and len(net_returns) != len(rows):
        return Result.insufficient_data("MODEL_NET_RETURN_LENGTH_MISMATCH")
    if regimes is not None and len(regimes) != len(rows):
        return Result.insufficient_data("MODEL_REGIME_LENGTH_MISMATCH")
    try:
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.isotonic import IsotonicRegression
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import brier_score_loss
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return Result.insufficient_data("SCIKIT_LEARN_NOT_INSTALLED")

    ordered = sorted(range(len(rows)), key=lambda index: observed_at[index])
    feature_names = tuple(sorted(set.intersection(*(set(rows[index]) for index in ordered))))
    if not feature_names:
        return Result.insufficient_data("MODEL_COMMON_FEATURES_MISSING")
    matrix = np.asarray([[float(rows[index][name]) for name in feature_names] for index in ordered])
    labels = np.asarray([int(bool(outcomes[index])) for index in ordered])
    if len(set(labels.tolist())) < 2:
        return Result.insufficient_data("MODEL_OUTCOME_CLASS_MISSING")
    train_end = int(len(ordered) * 0.70)
    validation_end = int(len(ordered) * 0.85)
    x_train, y_train = matrix[:train_end], labels[:train_end]
    x_validation, y_validation = matrix[train_end:validation_end], labels[train_end:validation_end]
    x_test, y_test = matrix[validation_end:], labels[validation_end:]

    baseline = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=17))
    baseline.fit(x_train, y_train)
    challenger = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=4, random_state=17)
    challenger.fit(x_train, y_train)
    baseline_validation = baseline.predict_proba(x_validation)[:, 1]
    challenger_validation = challenger.predict_proba(x_validation)[:, 1]
    baseline_brier = float(brier_score_loss(y_validation, baseline_validation))
    challenger_brier = float(brier_score_loss(y_validation, challenger_validation))
    selected = challenger if challenger_brier + 0.002 < baseline_brier else baseline
    selected_kind = "hist_gradient_boosting" if selected is challenger else "logistic_regression"
    calibration_method = "isotonic" if len(x_validation) >= 2000 else "sigmoid"
    test_raw = selected.predict_proba(x_test)[:, 1]
    if calibration_method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(selected.predict_proba(x_validation)[:, 1], y_validation)
        probabilities = calibrator.predict(test_raw)
        model_bundle: object = {"model": selected, "calibrator": calibrator, "method": calibration_method}
    else:
        slope, intercept = fit_sigmoid_calibrator(
            (selected.predict_proba(x_validation)[:, 1] * 100).tolist(),
            y_validation.tolist(),
        )
        probabilities = np.asarray([apply_sigmoid(value * 100, slope, intercept) for value in test_raw])
        model_bundle = {
            "model": selected,
            "calibrator": {"slope": slope, "intercept": intercept},
            "method": calibration_method,
        }
    champion_brier = float(brier_score_loss(y_test, probabilities))
    champion_ece = expected_calibration_error(probabilities.tolist(), y_test.tolist())
    naive_probability = float(y_train.mean())
    naive_brier = float(brier_score_loss(y_test, [naive_probability] * len(y_test)))
    selected_returns = (
        [float(net_returns[index]) for index in ordered[validation_end:]]
        if net_returns is not None
        else [1.0 if value else -1.0 for value in y_test.tolist()]
    )
    net_return_after_costs = mean(selected_returns)
    maximum_drawdown = _maximum_drawdown(selected_returns)
    selected_regimes = (
        [str(regimes[index]) for index in ordered[validation_end:]]
        if regimes is not None
        else ["all"] * len(selected_returns)
    )
    regime_returns: dict[str, list[float]] = {}
    for regime, value in zip(selected_regimes, selected_returns, strict=True):
        regime_returns.setdefault(regime, []).append(value)
    regime_means = [mean(values) for values in regime_returns.values()]
    regime_stability = 1.0 / (1.0 + (pstdev(regime_means) if len(regime_means) > 1 else 0.0))
    current = current_champion_metrics or {}
    promoted = (
        champion_brier < min(naive_brier, current.get("brier", float("inf")))
        and champion_ece <= 0.05
        and net_return_after_costs > current.get("net_return_after_costs", float("-inf"))
        and maximum_drawdown <= current.get("maximum_drawdown", float("inf"))
        and regime_stability >= current.get("regime_stability", float("-inf"))
    )
    reasons = (
        "MODEL_PROMOTION_GATES_PASSED"
        if promoted
        else "MODEL_REMAINS_CHALLENGER",
        "CHRONOLOGICAL_SPLIT",
        "NO_LOOKAHEAD_INPUT_ORDER",
    )
    report = TrainedModelReport(
        champion_kind=selected_kind,
        feature_names=feature_names,
        training_start=observed_at[ordered[0]],
        training_end=observed_at[ordered[train_end - 1]],
        training_samples=len(x_train),
        validation_samples=len(x_validation),
        test_samples=len(x_test),
        baseline_brier=baseline_brier,
        challenger_brier=challenger_brier,
        champion_brier=champion_brier,
        champion_ece=champion_ece,
        net_return_after_costs=net_return_after_costs,
        maximum_drawdown=maximum_drawdown,
        regime_stability=regime_stability,
        promoted=promoted,
        reason_codes=reasons,
        model=model_bundle,
    )
    return Result.success(report)


def _maximum_drawdown(returns: Sequence[float]) -> float:
    equity = peak = 1.0
    maximum = 0.0
    for value in returns:
        equity *= 1 + float(value) / 100.0
        peak = max(peak, equity)
        maximum = max(maximum, (peak - equity) / peak * 100.0)
    return maximum
