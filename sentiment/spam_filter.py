"""Local spam and shill repetition detection."""

from __future__ import annotations

from collections import Counter


def spam_repetition_score(snippets: tuple[str, ...] | list[str]) -> int:
    normalized = [_normalize(snippet) for snippet in snippets if _normalize(snippet)]
    if not normalized:
        return 0
    counts = Counter(normalized)
    repeats = sum(count - 1 for count in counts.values() if count > 1)
    shill_words = sum(
        1
        for snippet in normalized
        if any(word in snippet for word in ("100x", "moon", "ape now", "guaranteed", "send it"))
    )
    return min(100, repeats * 25 + shill_words * 10)


def _normalize(text: str) -> str:
    return " ".join(str(text).lower().strip().split())
