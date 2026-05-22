# Test Plan

## Expected Command

```bash
pytest
```

## Test Principles

- Tests must prove fail-closed behavior, not only happy paths.
- Safety regressions are first-class tests.
- Network adapters must be mockable and fixture-driven.
- Simulation accounting must be deterministic for fixed inputs.
- No test should require a paid API or real secret.

## Unit Tests

| Area | Expected Coverage |
| --- | --- |
| Config validation | Simulation defaults, `$50` capital, rejection of forbidden modes and invalid limits |
| Time and freshness | Stale timestamps, malformed timestamps, deterministic clock injection |
| TOON payload boundary | Safe compression, scrubbed fields, secret-like field rejection |
| Data validation | Missing fields, malformed numbers, unknown confidence, source provenance |
| Technical indicators | Sufficient lookback, insufficient lookback, deterministic feature output |
| Anti-rug rules | Every hard-fail rule vetoes new buy intent |
| Risk limits | Per-position cap, total exposure cap, max positions, unknown action handling |
| Intent parsing | Invalid agent output becomes non-actionable |
| Portfolio ledger | Simulated cash, holdings, and fill accounting |

## Integration Tests

| Flow | Expected Result |
| --- | --- |
| Valid fixture snapshot -> vector -> risk-approved simulated buy -> DuckDB | Audit rows, fill rows, and portfolio state are consistent |
| Stale snapshot -> vector/risk flow | `INSUFFICIENT_DATA`, no fill |
| Bullish intent plus anti-rug hard fail | Rejected buy, hard-fail reason persisted |
| Invalid agent payload -> orchestrator | `HOLD` or `INSUFFICIENT_DATA`, no broker action |
| Storage initialize -> write -> read | DuckDB schema supports core local records |

## Safety Tests

- Assert there is no live mode selectable in MVP settings.
- Assert forbidden live order actions are rejected by risk and broker boundaries.
- Assert withdrawals and transfers have no execution path.
- Assert raw LLM output cannot be submitted to the broker.
- Assert anti-rug vetoes outrank bullish features and agent confidence.
- Assert missing, stale, malformed, contradictory, or uncertain required data yields `INSUFFICIENT_DATA`.
- Assert secret-like values are excluded from prompt payloads, TOON payloads, memory, fixtures, logs, and storage boundaries.

## Simulation Tests

- Starting cash is exactly `$50` in the default paper portfolio.
- Approved fills reduce simulated cash and increase simulated holdings consistently.
- Rejected fills do not mutate portfolio state.
- Exposure caps prevent over-allocation across positions.
- Sell intents cannot sell holdings the paper portfolio does not own.
- Simulated price and quantity arithmetic uses a deliberate precision policy.

## Adapter Tests

- Use recorded safe fixtures or mocked transport responses.
- Verify source timestamp, provenance, confidence, malformed response, and network failure behavior.
- Verify adapter results have no order-execution authority.
- Verify optional adapters can be absent without breaking the core simulation path.

## Initial Test File Targets

- `tests/unit/test_risk_engine.py`
- `tests/unit/test_anti_rug.py`
- `tests/unit/test_vector_engine.py`
- `tests/unit/test_toon.py`
- `tests/integration/test_storage_flow.py`
- `tests/integration/test_simulation_flow.py`
- `tests/safety/test_no_live_trading.py`
- `tests/safety/test_no_secret_payloads.py`
- `tests/safety/test_insufficient_data.py`

## Completion Gate

Before an implementation phase is called complete:

1. Run `pytest`.
2. Report failures and skipped safety coverage.
3. Do not mark a phase complete if a hard safety invariant is untested after behavior that could violate it was introduced.

