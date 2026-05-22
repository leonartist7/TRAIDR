# Safety

TRAIDR is simulation-only. Safety constraints are enforced as product behavior and regression tests, not as operator convention.

## Hard Guarantees

- Live trading is not implemented.
- Withdrawals, transfers, bridging, custody, wallet signing, and private-key access are not implemented.
- LLM payloads reject secret-like keys before prompt construction.
- Raw LLM output cannot submit an order.
- `HOLD` is the default agent and risk-safe posture.
- Missing, stale, malformed, contradictory, or uncertain required data becomes `INSUFFICIENT_DATA`.
- Anti-rug hard fails override bullish signals and high-confidence intents.

## Deterministic Risk Limits

The MVP risk policy enforces a `$50` simulation bankroll, `$10` maximum position notional, `$30` maximum total exposure, three maximum open positions, and a `$5` daily loss halt before paper execution.

## Auditability

The paper broker records each simulation execution attempt and fill or block through DuckDB audit events. Stored execution payloads identify simulation mode and risk decision context while keeping secret-bearing data out of storage.
