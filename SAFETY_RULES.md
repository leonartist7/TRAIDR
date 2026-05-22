# Safety Rules

These rules are hard constraints for TRAIDR v3.1.

## Prohibited Capabilities

1. No live trading.
2. No withdrawals.
3. No private-key access.
4. No seed phrase access.
5. No wallet signing.
6. No secret exposure to LLMs, prompts, TOON payloads, logs, fixtures, DuckDB, or memory.
7. No direct LLM execution against an order API, broker API, DEX router, wallet, or signing path.

## Required Decision Behavior

1. Every `BUY` or `SELL` intent must pass deterministic validation before any simulation or future testnet action.
2. Deterministic risk code has final authority over agents, prompts, sentiment, and bullish technical signals.
3. The default action is `HOLD`.
4. Missing required data yields `INSUFFICIENT_DATA`.
5. Stale data yields `INSUFFICIENT_DATA`.
6. Malformed data yields `INSUFFICIENT_DATA`.
7. Contradictory or uncertain required data yields `INSUFFICIENT_DATA`.
8. Anti-rug hard fails override all bullish signals.

## Fail-Closed Rules

- A forbidden runtime mode must be rejected rather than silently downgraded.
- An unknown action must not be executed.
- An unapproved broker request must be rejected.
- A parser failure must not be treated as a confident trade signal.
- Unknown anti-rug status must block new entries when policy requires that evidence.
- Source failures must be recorded with reason codes where practical.

## Simulation Boundary

- MVP capital is simulated and starts at `$50`.
- Simulation fills exist for research and accounting only.
- Optional Hummingbot MCP work must remain simulation or explicit testnet only.
- Optional GOAT SDK and DexScreener modules are data-source boundaries unless a later testnet-only design is explicitly approved and still risk-gated.

## Review Gate

Any proposed code, config, documentation, or test fixture that weakens these rules is a safety regression and must be rejected or redesigned.
