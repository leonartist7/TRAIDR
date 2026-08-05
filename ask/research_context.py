"""Quarantined MCP research context for Ask TRAIDR.

Research text is untrusted, citation-only context. It has no scoring, risk, or
execution authority and is never persisted as unrestricted provider output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from urllib.parse import urlparse


_FORBIDDEN_ACTIONS = re.compile(
    r"\b(place|submit|cancel|reverse|execute|sign|withdraw|transfer|bridge|buy|sell|close|"
    r"change leverage)\b.{0,32}\b(order|trade|position|wallet|funds?|transaction|btc|eth|usdt)\b",
    re.IGNORECASE,
)
_PROMPT_INJECTION = re.compile(
    r"\b(ignore (all |any )?(previous|prior|system)|system prompt|developer message|reveal secrets?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResearchCitation:
    source: str
    url: str
    observed_at: datetime

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("research citations require a public HTTP(S) URL")
        if not self.source.strip():
            raise ValueError("research citations require a source")


@dataclass(frozen=True)
class ResearchContext:
    provider: str
    subject: str
    summary: str
    observed_at: datetime
    retrieved_at: datetime
    freshness: str
    citations: tuple[ResearchCitation, ...]
    status: str
    reason_codes: tuple[str, ...]
    scoring_weight: float = 0.0
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "subject": self.subject,
            "summary": self.summary,
            "observed_at": self.observed_at.isoformat(),
            "retrieved_at": self.retrieved_at.isoformat(),
            "freshness": self.freshness,
            "citations": [
                {"source": item.source, "url": item.url, "observed_at": item.observed_at.isoformat()}
                for item in self.citations
            ],
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "scoring_weight": 0.0,
            "can_execute_trades": False,
        }


def build_research_context(
    *,
    provider: str,
    subject: str,
    untrusted_text: str,
    observed_at: datetime,
    citations: tuple[ResearchCitation, ...],
    retrieved_at: datetime | None = None,
    maximum_age: timedelta = timedelta(minutes=15),
) -> ResearchContext:
    """Normalize bounded research context and fail closed on unsafe evidence."""

    now = retrieved_at or datetime.now(tz=UTC)
    reasons = ["MCP_RESEARCH_ONLY", "ZERO_SCORING_WEIGHT", "EXTERNAL_TEXT_UNTRUSTED"]
    summary = _bounded_text(untrusted_text)
    stale = observed_at > now or now - observed_at > maximum_age
    if stale:
        reasons.append("RESEARCH_CONTEXT_STALE")
    if not citations:
        reasons.append("RESEARCH_CITATION_MISSING")
    if _PROMPT_INJECTION.search(summary):
        summary = "External text quarantined because it contained instruction-like content."
        reasons.append("PROMPT_INJECTION_QUARANTINED")
    if _FORBIDDEN_ACTIONS.search(summary):
        summary = "External text quarantined because it requested an unsupported action."
        reasons.append("UNSUPPORTED_ACTION_REQUEST")
    usable = bool(citations) and not stale and not {
        "PROMPT_INJECTION_QUARANTINED",
        "UNSUPPORTED_ACTION_REQUEST",
    }.intersection(reasons)
    return ResearchContext(
        provider=provider.strip() or "unknown",
        subject=subject.strip() or "unknown",
        summary=summary,
        observed_at=observed_at,
        retrieved_at=now,
        freshness="FRESH" if usable else ("STALE" if stale else "UNKNOWN"),
        citations=citations,
        status="CONTEXT_ONLY" if usable else "INSUFFICIENT_DATA",
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def _bounded_text(value: str, *, maximum_length: int = 2_000) -> str:
    clean = " ".join(value.replace("\x00", " ").split())
    return clean[:maximum_length]
