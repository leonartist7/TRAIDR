"""Tiny local query parser for Ask TRAIDR."""

from __future__ import annotations

import re

from ask.intents import AskIntent


def parse_question(question: str) -> AskIntent:
    """Map a local natural-language question to a supported read-only intent."""

    text = _normalize(question)
    if not text:
        return AskIntent.UNKNOWN_QUESTION
    if any(term in text for term in ("risk", "risky", "danger", "avoid", "sell risk")):
        return AskIntent.TOP_RISKS
    if any(term in text for term in ("alert", "notification", "warning")):
        return AskIntent.RECENT_ALERTS
    if any(term in text for term in ("portfolio", "position", "exposure", "holdings")):
        return AskIntent.PORTFOLIO_SUMMARY
    if any(term in text for term in ("safety", "live trading", "withdrawal", "execution")):
        return AskIntent.SAFETY_STATUS
    if any(term in text for term in ("scan", "market scan", "evidence", "candidates found")):
        return AskIntent.SCAN_SUMMARY
    if any(term in text for term in ("opportunity", "best", "radar", "candidate", "watch today", "watchlist")):
        return AskIntent.TOP_OPPORTUNITIES
    return AskIntent.UNKNOWN_QUESTION


def _normalize(question: str) -> str:
    return re.sub(r"\s+", " ", str(question or "").strip().lower())
