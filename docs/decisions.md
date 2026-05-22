# Decisions

## Simulation Before Execution

TRAIDR uses a paper broker as the only MVP execution boundary. Live exchange routing and withdrawals stay absent instead of hidden behind config toggles.

## Risk Is Final Authority

Bounded research intents can suggest `BUY`, `SELL`, `HOLD`, or `INSUFFICIENT_DATA`, but the deterministic risk engine decides whether a paper action may continue.

## Local Deterministic Inputs

MVP scripts and tests use fixtures, mock gateways, deterministic timestamps, and DuckDB. Optional source adapters remain mockable and do not require paid APIs, network access, or keys.

## Compact Safe Payloads

Agent payloads use TOON only after unsafe secret-like payload keys are rejected. Raw model output must pass strict bounded intent parsing before risk evaluation.
