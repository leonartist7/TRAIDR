"""Fixture-first GOAT on-chain safety wrapper with injected transport only."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from onchain.contracts import OnchainSafetyObservation
from utils.results import Result

Transport = Callable[[str], Mapping[str, Any] | None]


class GoatSafetyAdapter:
    name = "goat_sdk"

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport

    def fetch_observation(self, token_ref: str) -> Result[OnchainSafetyObservation]:
        if self.transport is None:
            return Result.insufficient_data("GOAT_TRANSPORT_UNAVAILABLE")
        try:
            raw = self.transport(token_ref)
        except Exception:
            return Result.insufficient_data("GOAT_TRANSPORT_FAILED")
        if raw is None:
            return Result.insufficient_data("GOAT_SOURCE_MISSING")
        return Result.success(
            OnchainSafetyObservation(
                liquidity_accessible=_optional_bool(raw.get("liquidity_accessible")),
                liquidity_meets_floor=_optional_bool(raw.get("liquidity_meets_floor")),
                liquidity_status_known=_optional_bool(raw.get("liquidity_status_known")),
                mint_freeze_or_sell_restriction=_optional_bool(raw.get("mint_freeze_or_sell_restriction")),
                unsafe_holder_or_creator_control=_optional_bool(raw.get("unsafe_holder_or_creator_control")),
                honeypot_tax_route_or_sellability_issue=_optional_bool(
                    raw.get("honeypot_tax_route_or_sellability_issue")
                ),
                identity_ambiguous=_optional_bool(raw.get("identity_ambiguous")),
                evidence_complete=_optional_bool(raw.get("evidence_complete")),
            )
        )


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None

