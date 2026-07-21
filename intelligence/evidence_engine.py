"""Canonical, deduplicated context evidence and deterministic safety veto assembly."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha256
from math import exp
from typing import Any, Iterable, Mapping

from data_pipeline.asset_identity import AssetIdentityRegistry
from intelligence.production_models import EvidenceBundle, FeatureSnapshot
from onchain.contracts import OnchainSafetyObservation


SOURCE_RELIABILITY = {"coindesk": 0.90, "decrypt": 0.82, "cointelegraph": 0.78}
ALLOWLISTED_RSS_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "decrypt": "https://decrypt.co/feed",
    "cointelegraph": "https://cointelegraph.com/rss",
}


def normalize_headline(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", value.casefold()).split())


def map_news_evidence(
    rows: Iterable[Mapping[str, Any]],
    *,
    source: str,
    registry: AssetIdentityRegistry,
    now: datetime | None = None,
) -> tuple[dict[str, Any], ...]:
    if source not in SOURCE_RELIABILITY:
        return ()
    reference = now or datetime.now(tz=UTC)
    seen_urls: set[str] = set()
    seen_headlines: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for row in rows:
        headline = str(row.get("headline") or row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        normalized = normalize_headline(headline)
        normalized_url = url.casefold()
        if not headline or not url or normalized_url in seen_urls or normalized in seen_headlines:
            continue
        seen_urls.add(normalized_url)
        seen_headlines.add(normalized)
        published = _datetime(row.get("observed_at") or row.get("published_at"), reference)
        aliases = set(re.findall(r"[A-Za-z][A-Za-z0-9-]{1,20}", headline.upper()))
        candidates = [item for alias in aliases for item in registry.candidates_for_alias(alias)]
        matched = {item.canonical_asset_id: item for item in candidates}
        alias_ambiguous = any(len(registry.candidates_for_alias(alias)) > 1 for alias in aliases)
        mapping_state = "AMBIGUOUS" if alias_ambiguous or len(matched) > 1 else "VERIFIED" if len(matched) == 1 else "MISSING"
        asset_id = next(iter(matched)) if len(matched) == 1 else None
        age_hours = max(0.0, (reference - published).total_seconds() / 3600)
        age_weight = exp(-age_hours / 24.0)
        reliability = SOURCE_RELIABILITY[source]
        relevance = reliability * age_weight if asset_id else 0.0
        digest = sha256(f"{source}|{url}|{normalized}".encode()).hexdigest()[:24]
        evidence.append(
            {
                "evidence_id": f"news-{digest}",
                "canonical_asset_id": asset_id,
                "source": source,
                "headline": headline,
                "normalized_headline": normalized,
                "url": url,
                "published_at": published,
                "observed_at": reference,
                "reliability": reliability,
                "relevance": relevance,
                "age_weight": age_weight,
                "mapping_state": mapping_state,
                "reason_codes": (
                    "NEWS_CONTEXT_ONLY",
                    "NEWS_ENTITY_EXACT" if asset_id else "NEWS_ENTITY_NOT_ACTIONABLE",
                ),
            }
        )
    return tuple(evidence)


def onchain_hard_vetoes(observation: OnchainSafetyObservation | None) -> tuple[str, ...]:
    if observation is None:
        return ()
    vetoes: list[str] = []
    if observation.honeypot_tax_route_or_sellability_issue is True:
        vetoes.append("ONCHAIN_HONEYPOT_OR_SELL_RESTRICTION")
    if observation.liquidity_accessible is False:
        vetoes.append("ONCHAIN_LIQUIDITY_INACCESSIBLE")
    if observation.mint_freeze_or_sell_restriction is True:
        vetoes.append("ONCHAIN_FREEZE_OR_SELL_RESTRICTION")
    if observation.unsafe_holder_or_creator_control is True:
        vetoes.append("ONCHAIN_UNSAFE_CONTROL")
    if observation.identity_ambiguous is True:
        vetoes.append("CONTRADICTORY_ASSET_IDENTITY")
    return tuple(vetoes)


def build_evidence_bundle(
    feature: FeatureSnapshot,
    *,
    canonical_asset_id: str | None,
    microstructure: Mapping[str, Any] | None = None,
    futures_crowding: Mapping[str, Any] | None = None,
    cross_market: Mapping[str, Any] | None = None,
    news: tuple[dict[str, Any], ...] = (),
    onchain: Mapping[str, Any] | None = None,
    onchain_observation: OnchainSafetyObservation | None = None,
    generated_at: datetime | None = None,
) -> EvidenceBundle:
    components = {
        "technical": bool(feature.features),
        "microstructure": bool(microstructure),
        "futures_crowding": bool(futures_crowding),
        "cross_market": bool(cross_market),
        "news": bool(news),
        "onchain": bool(onchain),
    }
    weights = {
        "technical": 0.30,
        "microstructure": 0.20,
        "futures_crowding": 0.20,
        "cross_market": 0.15,
        "news": 0.05,
        "onchain": 0.10,
    }
    missing = tuple(name for name, present in components.items() if not present)
    coverage = min(feature.data_coverage, sum(weights[name] for name, present in components.items() if present))
    vetoes = onchain_hard_vetoes(onchain_observation)
    contradictions = feature.contradiction_flags
    digest = sha256(
        f"{feature.feature_id}|{canonical_asset_id}|{feature.observed_at.isoformat()}".encode()
    ).hexdigest()[:24]
    evidence_ids = tuple(dict.fromkeys((*feature.evidence_ids, *(str(item["evidence_id"]) for item in news))))
    return EvidenceBundle(
        bundle_id=f"evidence-{digest}",
        instrument_id=feature.instrument_id,
        canonical_asset_id=canonical_asset_id,
        observed_at=feature.observed_at,
        generated_at=generated_at or datetime.now(tz=UTC),
        feature_version=feature.feature_version,
        technical=feature.features,
        microstructure=dict(microstructure or {}),
        futures_crowding=dict(futures_crowding or {}),
        cross_market=dict(cross_market or {}),
        news=news,
        onchain=dict(onchain or {}),
        data_coverage=coverage,
        missing_components=missing,
        contradiction_flags=contradictions,
        hard_vetoes=vetoes,
        evidence_ids=evidence_ids or (feature.feature_id,),
        reason_codes=("EVIDENCE_BUNDLE_DETERMINISTIC", "NEWS_CANNOT_CREATE_DIRECTION"),
    )


def _datetime(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return fallback
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
