"""Reviewed exact asset identities; symbol-only cross-source joins are forbidden."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, Literal

from intelligence.production_models import CanonicalAssetIdentity, MappingReviewState, SourceBinding


REVIEWED_AT = datetime(2026, 7, 21, tzinfo=UTC)


def reviewed_seed_identities() -> tuple[CanonicalAssetIdentity, ...]:
    return (
        CanonicalAssetIdentity(
            canonical_asset_id="asset:bitcoin",
            symbol="BTC",
            name="Bitcoin",
            aliases=("BTC", "BITCOIN"),
            reviewed_at=REVIEWED_AT,
            reason_codes=("IDENTITY_MANUALLY_REVIEWED",),
        ),
        CanonicalAssetIdentity(
            canonical_asset_id="asset:hyperliquid",
            symbol="HYPE",
            name="Hyperliquid",
            aliases=("HYPE", "HYPERLIQUID"),
            reviewed_at=REVIEWED_AT,
            reason_codes=("IDENTITY_MANUALLY_REVIEWED",),
        ),
    )


def reviewed_seed_bindings() -> tuple[SourceBinding, ...]:
    rows: tuple[tuple[str, str, Literal["futures_symbol", "spot_id"], str], ...] = (
        ("asset:bitcoin", "bitunix", "futures_symbol", "BTCUSDT"),
        ("asset:bitcoin", "coingecko", "spot_id", "bitcoin"),
        ("asset:hyperliquid", "bitunix", "futures_symbol", "HYPEUSDT"),
        ("asset:hyperliquid", "coingecko", "spot_id", "hyperliquid"),
    )
    return tuple(
        SourceBinding(
            binding_id=f"binding:{source}:{kind}:{identifier.lower()}",
            canonical_asset_id=asset_id,
            source=source,
            binding_kind=kind,
            source_identifier=identifier,
            review_state=MappingReviewState.VERIFIED,
            reviewed_at=REVIEWED_AT,
            provenance="TRAIDR reviewed seed mapping 0.2.0",
            reason_codes=("EXACT_SOURCE_BINDING", "SYMBOL_ONLY_JOIN_FORBIDDEN"),
        )
        for asset_id, source, kind, identifier in rows
    )


class AssetIdentityRegistry:
    def __init__(
        self,
        identities: Iterable[CanonicalAssetIdentity] = (),
        bindings: Iterable[SourceBinding] = (),
    ) -> None:
        self.identities = {item.canonical_asset_id: item for item in identities}
        self.bindings = tuple(bindings)

    @classmethod
    def reviewed_defaults(cls) -> "AssetIdentityRegistry":
        return cls(reviewed_seed_identities(), reviewed_seed_bindings())

    def resolve(
        self,
        *,
        source: str,
        binding_kind: str,
        source_identifier: str,
        chain_id: str | None = None,
    ) -> CanonicalAssetIdentity | None:
        candidates = [
            binding
            for binding in self.bindings
            if binding.review_state is MappingReviewState.VERIFIED
            and binding.source.casefold() == source.casefold()
            and binding.binding_kind == binding_kind
            and binding.source_identifier.casefold() == source_identifier.casefold()
            and (binding.chain_id or "").casefold() == (chain_id or "").casefold()
        ]
        if len(candidates) != 1:
            return None
        return self.identities.get(candidates[0].canonical_asset_id)

    def bindings_for(self, canonical_asset_id: str) -> tuple[SourceBinding, ...]:
        return tuple(
            binding
            for binding in self.bindings
            if binding.canonical_asset_id == canonical_asset_id
            and binding.review_state is MappingReviewState.VERIFIED
        )

    def match_alias(self, token: str) -> CanonicalAssetIdentity | None:
        candidates = self.candidates_for_alias(token)
        return candidates[0] if len(candidates) == 1 else None

    def candidates_for_alias(self, token: str) -> tuple[CanonicalAssetIdentity, ...]:
        normalized = token.strip().upper()
        candidates = [
            identity
            for identity in self.identities.values()
            if identity.review_state is MappingReviewState.VERIFIED
            and normalized in {alias.upper() for alias in identity.aliases}
        ]
        return tuple(candidates)
