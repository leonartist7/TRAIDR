"""Rank local watchlist candidates without execution authority."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from agents.opportunity_ranker import rank_opportunity
from radar.models import RadarCandidate
from radar.state_machine import classify_opportunity
from radar.watchlist import normalize_watchlist


def rank_watchlist(records: Iterable[Mapping[str, Any]]) -> tuple[RadarCandidate, ...]:
    candidates: list[RadarCandidate] = []
    for record in normalize_watchlist(records):
        ranking = rank_opportunity(record["analyses"])
        if record.get("sentiment_missing"):
            ranking = type(ranking)(
                opportunity_score=ranking.opportunity_score,
                risk_score=ranking.risk_score,
                confidence=max(0.0, round(ranking.confidence - 0.1, 4)),
                missing_critical_count=ranking.missing_critical_count + 1,
                conflict_detected=ranking.conflict_detected,
                reason_codes=tuple(dict.fromkeys((*ranking.reason_codes, "SENTIMENT_MISSING_NOT_BULLISH"))),
            )
        state, state_reasons = classify_opportunity(
            opportunity_score=ranking.opportunity_score,
            risk_score=ranking.risk_score,
            confidence=ranking.confidence,
            missing_critical_count=ranking.missing_critical_count,
            conflict_detected=ranking.conflict_detected,
        )
        candidates.append(
            RadarCandidate(
                subject_id=record["subject_id"],
                state=state,
                rank=0,
                opportunity_score=ranking.opportunity_score,
                risk_score=ranking.risk_score,
                confidence=ranking.confidence,
                reason_codes=tuple(dict.fromkeys((*ranking.reason_codes, *state_reasons))),
            )
        )
    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate.state.value == "AVOID",
            -candidate.opportunity_score,
            candidate.risk_score,
            -candidate.confidence,
            candidate.subject_id,
        ),
    )
    return tuple(
        RadarCandidate(
            subject_id=candidate.subject_id,
            state=candidate.state,
            rank=index,
            opportunity_score=candidate.opportunity_score,
            risk_score=candidate.risk_score,
            confidence=candidate.confidence,
            reason_codes=candidate.reason_codes,
        )
        for index, candidate in enumerate(sorted_candidates, start=1)
    )
