"""Bounded mock research agent boundary."""

from __future__ import annotations

from pathlib import Path

from agents.llm_gateway import MockResearchGateway

_DEFAULT_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "system_research.md"


class ResearchAgent:
    def __init__(
        self,
        gateway: MockResearchGateway | None = None,
        *,
        prompt_path: str | Path = _DEFAULT_PROMPT,
    ) -> None:
        self.gateway = gateway or MockResearchGateway()
        self.prompt_path = Path(prompt_path)

    def propose(self, payload_toon: str) -> str:
        return self.gateway.complete(
            system_prompt=self.prompt_path.read_text(encoding="utf-8"),
            payload_toon=payload_toon,
        )

