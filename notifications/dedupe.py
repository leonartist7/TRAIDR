"""Alert deduplication helpers."""

from __future__ import annotations

from collections.abc import Iterable

from notifications.models import Alert


class AlertDeduper:
    def __init__(self, existing_fingerprints: Iterable[str] = ()) -> None:
        self._seen = set(existing_fingerprints)

    def should_send(self, alert: Alert) -> bool:
        fingerprint = alert.fingerprint
        if fingerprint in self._seen:
            return False
        self._seen.add(fingerprint)
        return True

