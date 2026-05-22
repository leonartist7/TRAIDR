"""Scrubbed local bounded research memory."""

from __future__ import annotations

from dataclasses import dataclass, field

from agents.intents import BoundedIntent
from utils.toon import JsonValue, assert_safe_payload


@dataclass
class ResearchMemory:
    records: list[dict[str, JsonValue]] = field(default_factory=list)

    def remember(self, *, pair_id: str, intent: BoundedIntent) -> None:
        record: dict[str, JsonValue] = {
            "pair": pair_id,
            "intent": intent.action.value,
            "confidence": intent.confidence.value,
            "reasons": list(intent.reason_codes),
        }
        assert_safe_payload(record)
        self.records.append(record)

