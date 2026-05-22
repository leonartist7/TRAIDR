"""Map on-chain safety observations into anti-rug risk evidence."""

from __future__ import annotations

from onchain.contracts import OnchainSafetyObservation
from risk.models import AntiRugEvidence


def to_anti_rug_evidence(observation: OnchainSafetyObservation | None) -> AntiRugEvidence:
    if observation is None:
        return AntiRugEvidence(
            liquidity_accessible=None,
            liquidity_meets_floor=None,
            liquidity_status_known=None,
            mint_freeze_or_sell_restriction=None,
            unsafe_holder_or_creator_control=None,
            honeypot_tax_route_or_sellability_issue=None,
            identity_ambiguous=None,
            evidence_complete=None,
        )
    return AntiRugEvidence(
        liquidity_accessible=observation.liquidity_accessible,
        liquidity_meets_floor=observation.liquidity_meets_floor,
        liquidity_status_known=observation.liquidity_status_known,
        mint_freeze_or_sell_restriction=observation.mint_freeze_or_sell_restriction,
        unsafe_holder_or_creator_control=observation.unsafe_holder_or_creator_control,
        honeypot_tax_route_or_sellability_issue=observation.honeypot_tax_route_or_sellability_issue,
        identity_ambiguous=observation.identity_ambiguous,
        evidence_complete=observation.evidence_complete,
    )

