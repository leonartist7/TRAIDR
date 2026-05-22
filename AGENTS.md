# AGENTS.md

## Repository Mission

TRAIDR is a simulation-first micro-cap crypto intelligence and paper-trading research engine. Treat safety rules as product requirements, not optional guidance.

## Codex Instructions

- Target Python 3.11 for future runtime code.
- Keep the repository simulation-first and local-first.
- Do not implement live trading.
- Do not implement withdrawals, transfers, bridging, or custody flows.
- Do not add private-key, seed phrase, wallet signing, or secret-access code.
- Do not expose API keys, credentials, private keys, or secret-bearing environment variables to LLM prompts, TOON payloads, memory, logs, fixtures, or DuckDB.
- Keep deterministic risk validation as the final authority before any simulation or future testnet execution path.
- Never allow raw LLM output to execute orders.
- Default to `HOLD`.
- Return `INSUFFICIENT_DATA` when data is missing, stale, malformed, contradictory, or uncertain.
- Make anti-rug hard failures override bullish signals.
- Prefer DuckDB for future local persistence.
- Use TOON only for safe compressed LLM payloads.
- Run `pytest` after future code changes and report when tests cannot be run.
- Do not overbuild beyond the requested implementation phase.

## Phase Discipline

- During planning-only work, create Markdown planning artifacts only.
- During bootstrap, create structure and tooling without silently implementing later phases.
- Add optional adapters behind safe boundaries and keep network behavior mockable.
- Preserve explicit reason codes and auditability when implementing decisions.
- Keep forbidden capabilities absent rather than hidden behind flags.

## Editing Notes

- Read the current phase documents before adding runtime modules.
- Keep changes scoped to the active phase acceptance criteria.
- Add focused tests when behavior changes.
- If a requested change conflicts with `SAFETY_RULES.md`, stop and explain the conflict.
