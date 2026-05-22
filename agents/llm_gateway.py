"""Mockable research gateway with no provider calls."""

from __future__ import annotations

import json
from collections.abc import Callable

GatewayCallable = Callable[[str, str], str]


class MockResearchGateway:
    """Default gateway returns bounded HOLD output."""

    def __init__(self, responder: GatewayCallable | None = None) -> None:
        self.responder = responder
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system_prompt: str, payload_toon: str) -> str:
        self.calls.append((system_prompt, payload_toon))
        if self.responder is not None:
            return self.responder(system_prompt, payload_toon)
        return json.dumps(
            {
                "intent": "HOLD",
                "confidence": "unknown",
                "reason_codes": ["MOCK_DEFAULT_HOLD"],
                "evidence_summary": ["mock gateway has no trading authority"],
                "risk_handoff_required": True,
            }
        )

