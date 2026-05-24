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

## Git Publishing

- After completing an implementation request, run the relevant tests.
- If tests pass, stage the files changed for the request, create a concise commit, and push `main` to `origin` unless the user explicitly says not to push or names another branch.
- Do not push when tests fail or when unrelated working-tree changes cannot be safely separated.
- Report the commit SHA and push result in the final response.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. If `graphify` is not on PATH, use `python -m graphify query "<question>"`. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` or `python -m graphify update .` to keep the graph current (AST-only, no API cost).
