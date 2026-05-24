"""Optional static contract scanner JSON mapping into anti-rug observations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from onchain.contracts import OnchainSafetyObservation
from utils.results import Result


@dataclass(frozen=True)
class StaticContractRiskAnalysis:
    """Contract privilege flags parsed from optional static JSON input."""

    mint_freeze_or_sell_restriction: bool | None
    unsafe_holder_or_creator_control: bool | None
    honeypot_tax_route_or_sellability_issue: bool | None
    reason_codes: tuple[str, ...]

    def to_observation(self) -> OnchainSafetyObservation:
        complete = all(
            value is not None
            for value in (
                self.mint_freeze_or_sell_restriction,
                self.unsafe_holder_or_creator_control,
                self.honeypot_tax_route_or_sellability_issue,
            )
        )
        return OnchainSafetyObservation(
            mint_freeze_or_sell_restriction=self.mint_freeze_or_sell_restriction,
            unsafe_holder_or_creator_control=self.unsafe_holder_or_creator_control,
            honeypot_tax_route_or_sellability_issue=self.honeypot_tax_route_or_sellability_issue,
            evidence_complete=complete,
        )


def analyze_static_contract_risk(
    scanner_json: Mapping[str, Any] | None,
) -> Result[StaticContractRiskAnalysis]:
    """Parse optional scanner JSON without requiring an external scanner."""

    if scanner_json is None:
        return Result.insufficient_data("STATIC_SCANNER_OUTPUT_MISSING")
    flags = scanner_json.get("flags", scanner_json)
    if not isinstance(flags, Mapping):
        return Result.insufficient_data("STATIC_SCANNER_OUTPUT_MALFORMED")

    mint_or_freeze = _flag(flags, "mint_authority") or _flag(flags, "freeze_authority")
    owner_control = _flag(flags, "owner_can_change_fees") or _flag(flags, "owner_can_blacklist")
    sellability = _flag(flags, "honeypot") or _flag(flags, "sell_tax_high") or _flag(flags, "transfer_restricted")
    unknown = any(
        value is None
        for value in (
            _flag(flags, "mint_authority"),
            _flag(flags, "freeze_authority"),
            _flag(flags, "owner_can_change_fees"),
            _flag(flags, "owner_can_blacklist"),
            _flag(flags, "honeypot"),
            _flag(flags, "sell_tax_high"),
            _flag(flags, "transfer_restricted"),
        )
    )
    reasons: list[str] = []
    if mint_or_freeze:
        reasons.append("STATIC_MINT_OR_FREEZE_PRIVILEGE")
    if owner_control:
        reasons.append("STATIC_OWNER_CONTROL_PRIVILEGE")
    if sellability:
        reasons.append("STATIC_SELLABILITY_RESTRICTION")
    if unknown:
        reasons.append("STATIC_SCANNER_FIELDS_UNKNOWN")
    if not reasons:
        reasons.append("STATIC_CONTRACT_FLAGS_CLEAR")

    return Result.success(
        StaticContractRiskAnalysis(
            mint_freeze_or_sell_restriction=_unknown_or_bool(mint_or_freeze, unknown),
            unsafe_holder_or_creator_control=_unknown_or_bool(owner_control, unknown),
            honeypot_tax_route_or_sellability_issue=_unknown_or_bool(sellability, unknown),
            reason_codes=tuple(reasons),
        )
    )


def _flag(flags: Mapping[str, Any], key: str) -> bool | None:
    value = flags.get(key)
    return value if isinstance(value, bool) else None


def _unknown_or_bool(value: bool | None, unknown: bool) -> bool | None:
    if value is True:
        return True
    return None if unknown else False
