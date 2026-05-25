"""Generate structured research notes for radar candidates."""

from __future__ import annotations

from thesis.invalidation import build_exit_warning_conditions, build_invalidation_conditions
from thesis.models import ResearchThesis, ThesisInputs


def generate_research_thesis(inputs: ThesisInputs) -> ResearchThesis:
    """Create a conservative, non-advisory research thesis."""

    data_gaps = _data_gaps(inputs)
    reasons = ["THESIS_RESEARCH_NOTES_GENERATED"]
    if data_gaps:
        reasons.append("THESIS_DATA_GAPS_PRESENT")
    risk_factors = _risk_factors(inputs, data_gaps)
    drivers = _opportunity_drivers(inputs)
    confidence = _confidence(inputs, data_gaps)
    summary = _summary(inputs, data_gaps)
    return ResearchThesis(
        subject_id=inputs.subject_id,
        thesis_summary=summary,
        opportunity_drivers=drivers,
        risk_factors=risk_factors,
        invalidation_conditions=build_invalidation_conditions(inputs),
        watch_conditions=_watch_conditions(inputs),
        exit_warning_conditions=build_exit_warning_conditions(inputs),
        confidence=confidence,
        data_gaps=data_gaps,
        reason_codes=tuple(dict.fromkeys((*reasons, *inputs.reason_codes))),
    )


def _summary(inputs: ThesisInputs, data_gaps: tuple[str, ...]) -> str:
    state = inputs.radar_state or "UNKNOWN"
    if data_gaps:
        return (
            f"{inputs.subject_id} has incomplete research context, so the thesis is limited to watch-only notes. "
            f"Current radar state is {state}; missing data must be resolved before confidence can improve."
        )
    return (
        f"{inputs.subject_id} is a {state} research candidate with opportunity score "
        f"{_fmt(inputs.opportunity_score)} and risk score {_fmt(inputs.risk_score)}."
    )


def _opportunity_drivers(inputs: ThesisInputs) -> tuple[str, ...]:
    drivers: list[str] = []
    if _number(inputs.opportunity_score) >= 60:
        drivers.append("Radar opportunity score is elevated versus the local research threshold.")
    if _number(inputs.risk_adjusted_score) >= 45:
        drivers.append("Risk-adjusted score remains constructive after deterministic caps.")
    if _number(inputs.technical_score) >= 60:
        drivers.append("Technical score suggests positive local momentum.")
    if _number(inputs.liquidity_score) >= 60:
        drivers.append("Liquidity score is adequate for continued observation.")
    return tuple(drivers or ("No strong opportunity driver is confirmed from the available data.",))


def _risk_factors(inputs: ThesisInputs, data_gaps: tuple[str, ...]) -> tuple[str, ...]:
    factors: list[str] = []
    if data_gaps:
        factors.append("Missing data limits thesis confidence.")
    if inputs.safety_status is None or str(inputs.safety_status).upper() not in {"CLEAR", "OK", "SAFE"}:
        factors.append("Safety evidence is not fully clear.")
    if _number(inputs.risk_score) >= 60:
        factors.append("Risk score is elevated.")
    if _number(inputs.liquidity_score) < 40:
        factors.append("Liquidity score is low enough to make exits harder to model.")
    if _number(inputs.risk_adjusted_score) < 30:
        factors.append("Risk-adjusted score is weak after safety and liquidity caps.")
    return tuple(dict.fromkeys(factors or ("Research risk remains present even when no hard risk factor is detected.",)))


def _watch_conditions(inputs: ThesisInputs) -> tuple[str, ...]:
    conditions = [
        "Watch for fresher market, safety, and liquidity evidence.",
        "Watch whether radar state improves without risk score increasing.",
    ]
    if _number(inputs.opportunity_score) < 60:
        conditions.append("Watch for opportunity score to improve before treating the candidate as high priority research.")
    if _number(inputs.liquidity_score) < 60:
        conditions.append("Watch liquidity depth and consistency before increasing attention.")
    return tuple(dict.fromkeys(conditions))


def _data_gaps(inputs: ThesisInputs) -> tuple[str, ...]:
    gaps = list(inputs.data_gaps)
    required = {
        "radar_state": inputs.radar_state,
        "opportunity_score": inputs.opportunity_score,
        "risk_score": inputs.risk_score,
        "safety_status": inputs.safety_status,
    }
    for field, value in required.items():
        if value is None:
            gaps.append(f"MISSING_{field.upper()}")
    return tuple(dict.fromkeys(gaps))


def _confidence(inputs: ThesisInputs, data_gaps: tuple[str, ...]) -> float:
    base = 0.0 if inputs.confidence is None else max(0.0, min(1.0, float(inputs.confidence)))
    if data_gaps:
        base = min(base, 0.35)
    if _number(inputs.risk_score) >= 75:
        base = min(base, 0.45)
    return round(base, 4)


def _number(value: float | None) -> float:
    return 0.0 if value is None else float(value)


def _fmt(value: float | None) -> str:
    return "unknown" if value is None else f"{float(value):.1f}"
