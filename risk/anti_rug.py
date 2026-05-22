"""Anti-rug hard-fail vetoes for the deterministic risk engine."""

from __future__ import annotations

from dataclasses import dataclass

from risk.models import AntiRugEvidence

_UNKNOWN_REASON = "ANTI_RUG_EVIDENCE_INSUFFICIENT"


@dataclass(frozen=True)
class AntiRugAssessment:
    """Fail-first anti-rug assessment."""

    hard_fail_reasons: tuple[str, ...]
    insufficient_data_reasons: tuple[str, ...]

    @property
    def hard_failed(self) -> bool:
        return bool(self.hard_fail_reasons)

    @property
    def insufficient_data(self) -> bool:
        return bool(self.insufficient_data_reasons)


def assess_anti_rug(evidence: AntiRugEvidence) -> AntiRugAssessment:
    """Return hard fail reasons before any bullish signal is considered."""

    hard_fails: list[str] = []
    insufficient: list[str] = []

    _require_safe_false(
        evidence.mint_freeze_or_sell_restriction,
        "ANTI_RUG_MINT_FREEZE_OR_SELL_RESTRICTION",
        hard_fails,
        insufficient,
    )
    _require_safe_false(
        evidence.unsafe_holder_or_creator_control,
        "ANTI_RUG_HOLDER_OR_CREATOR_CONTROL",
        hard_fails,
        insufficient,
    )
    _require_safe_false(
        evidence.honeypot_tax_route_or_sellability_issue,
        "ANTI_RUG_HONEYPOT_OR_SELLABILITY",
        hard_fails,
        insufficient,
    )
    _require_safe_false(
        evidence.identity_ambiguous,
        "ANTI_RUG_IDENTITY_AMBIGUOUS",
        hard_fails,
        insufficient,
    )
    _require_safe_true(
        evidence.liquidity_accessible,
        "ANTI_RUG_LIQUIDITY_INACCESSIBLE",
        hard_fails,
        insufficient,
    )
    _require_safe_true(
        evidence.liquidity_meets_floor,
        "ANTI_RUG_LIQUIDITY_BELOW_FLOOR",
        hard_fails,
        insufficient,
    )
    _require_safe_true(
        evidence.liquidity_status_known,
        "ANTI_RUG_LIQUIDITY_STATUS_UNKNOWN",
        hard_fails,
        insufficient,
    )
    _require_safe_true(
        evidence.evidence_complete,
        "ANTI_RUG_REQUIRED_EVIDENCE_INCOMPLETE",
        hard_fails,
        insufficient,
    )

    return AntiRugAssessment(tuple(hard_fails), tuple(dict.fromkeys(insufficient)))


def _require_safe_true(
    value: bool | None,
    hard_fail_reason: str,
    hard_fails: list[str],
    insufficient: list[str],
) -> None:
    if value is False:
        hard_fails.append(hard_fail_reason)
    elif value is None:
        insufficient.append(_UNKNOWN_REASON)


def _require_safe_false(
    value: bool | None,
    hard_fail_reason: str,
    hard_fails: list[str],
    insufficient: list[str],
) -> None:
    if value is True:
        hard_fails.append(hard_fail_reason)
    elif value is None:
        insufficient.append(_UNKNOWN_REASON)

