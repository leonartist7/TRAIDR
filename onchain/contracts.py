"""On-chain safety observation contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnchainSafetyObservation:
    liquidity_accessible: bool | None = None
    liquidity_meets_floor: bool | None = None
    liquidity_status_known: bool | None = None
    mint_freeze_or_sell_restriction: bool | None = None
    unsafe_holder_or_creator_control: bool | None = None
    honeypot_tax_route_or_sellability_issue: bool | None = None
    identity_ambiguous: bool | None = None
    evidence_complete: bool | None = None

