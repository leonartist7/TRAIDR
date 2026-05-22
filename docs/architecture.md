# Architecture

TRAIDR is a local simulation research engine with explicit boundaries between observations, model-assisted research, deterministic risk, and paper execution.

## MVP Flow

1. The data pipeline normalizes source or fixture records into `NormalizedMarketSnapshot` values with identity, metrics, provenance, and freshness fields.
2. The technical vector engine turns deterministic OHLCV candles into compact TOON-safe features.
3. On-chain helpers produce anti-rug evidence for deterministic veto checks.
4. The research agent receives a scrubbed TOON payload and returns a bounded intent through a mockable gateway.
5. `RiskEngine` evaluates data quality, freshness, anti-rug evidence, confidence, mode, bankroll, exposure, open positions, and daily loss.
6. `SimulationBroker` accepts only approved risk decisions and records paper orders, fills, and audit events in DuckDB.

## Boundaries

- Raw adapter payloads do not enter risk or execution directly.
- Raw LLM text is parsed into bounded intents before risk validation.
- No execution path exists for live exchange orders, withdrawals, custody, signing, or private-key access.
- DuckDB is local storage for research evidence, technical vectors, intents, risk decisions, paper records, and audit events.

## Optional Sources

DexScreener and GOAT modules are safe adapter wrappers in this MVP. They are fixture-first, mockable, and must fail closed when input is missing, stale, contradictory, or uncertain.
