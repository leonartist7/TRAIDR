# Implementation Plan

## Guiding Order

Build deterministic safety foundations before adapters and agent orchestration. The project should be useful in simulation even when every optional network source is unavailable.

| Phase | Files to Create | Dependencies | Acceptance Criteria | Failure Handling | Deferred Beyond MVP |
| --- | --- | --- | --- | --- | --- |
| 0. Bootstrap | `pyproject.toml`, package `__init__.py` files, test layout | Planning docs | Python 3.11 project skeleton exists and `pytest` can discover tests | Stop if tooling selects an unsafe or unsupported runtime | Packaging polish, release automation |
| 1. Configs | `config/settings.py`, `config/defaults.toml`, `config/risk_limits.toml` | Bootstrap | Default mode is simulation, bankroll is `$50`, forbidden modes fail validation | Reject invalid config and use explicit reason messages | Multi-profile environments |
| 2. Core utilities | `utils/clocks.py`, `utils/results.py`, `utils/logging.py`, `utils/toon.py` | Config contracts | Freshness and TOON boundaries are deterministic and testable | Fail closed on malformed timestamps and secret-like payload fields | Advanced telemetry |
| 3. Storage | `storage/duckdb_store.py`, `storage/schema.py`, `storage/repositories.py` | Bootstrap, utilities | DuckDB can persist audit-safe evidence, intents, risk decisions, and simulated fills | Surface storage errors without fabricating decisions | Migration framework beyond local MVP |
| 4. Risk engine | `risk/models.py`, `risk/anti_rug.py`, `risk/limits.py`, `risk/engine.py` | Configs, utilities | Risk engine blocks hard fails, stale data, over-limit exposure, and forbidden actions | Return rejection or `INSUFFICIENT_DATA` with reason codes | Portfolio optimization |
| 5. Simulation broker | `execution/models.py`, `execution/portfolio.py`, `execution/simulation_broker.py` | Risk engine, storage | Only risk-approved simulated instructions change paper portfolio state | Reject unapproved or inconsistent broker requests | Live broker integrations |
| 6. Technical vector engine | `technicals/indicators.py`, `technicals/vector_engine.py` | Data contracts, utilities | Fixed inputs yield fixed vectors and missing lookback fails closed | Emit `INSUFFICIENT_DATA` for unsupported feature calculations | High-frequency feature research |
| 7. Data adapters | `data_pipeline/contracts.py`, `data_pipeline/validation.py`, `data_pipeline/normalization.py`, `data_pipeline/source_registry.py`, optional source adapters, `onchain/*` | Configs, utilities, storage contracts | Free-source data is normalized with provenance and failures are explicit | Do not infer safety from adapter silence or network failure | Paid APIs, broad chain coverage |
| 8. Agent orchestration | `agents/intents.py`, `agents/orchestrator.py`, `agents/llm_gateway.py`, `agents/research_agent.py`, `prompts/*`, `memory/research_memory.py` | Vectors, risk interface, TOON utility | Agent output is bounded, scrubbed, and risk-gated with `HOLD` fallback | Invalid output becomes non-actionable | Multi-agent tuning, autonomous scheduling |
| 9. Tests | `tests/unit/*`, `tests/integration/*`, `tests/safety/*`, `tests/conftest.py` | Implemented modules | `pytest` covers safety and paper-flow behavior | Block phase completion on safety regression | Load and soak suites |
| 10. README/docs | `docs/architecture.md`, `docs/safety.md`, `docs/decisions.md`, README updates | Stable MVP behavior | Docs describe actual local commands and safety guarantees | Mark placeholders until commands exist | Public deployment docs |

## Phase Notes

### Phase 0: Bootstrap

- Keep the skeleton light.
- Select only dependencies justified by local MVP needs.
- Do not add runtime adapters or config values before config validation exists.

### Phase 1: Configs

- Separate editable defaults from hard prohibitions.
- Ensure no config file can switch to live trading.
- Keep risk limits test-visible.

### Phase 2: Utilities

- Centralize freshness and result semantics early so later modules share one fail-closed vocabulary.
- Add TOON handling as a safe serialization boundary, not as a secret transport.

### Phase 3: Storage

- Store evidence and audit events before complex orchestration.
- Prefer explicit schema initialization over hidden side effects.

### Phase 4: Risk Engine

- Implement anti-rug vetoes before positive scoring paths.
- Keep risk decisions deterministic and explainable.

### Phase 5: Simulation Broker

- Model cash, holdings, simulated fills, and rejection paths.
- Do not let broker methods accept raw natural-language content.

### Phase 6: Technical Vector Engine

- Keep feature calculation independent from LLM prompts.
- Carry source freshness and feature quality flags.

### Phase 7: Data Adapters

- Implement adapter contracts before concrete free-source modules.
- Treat GOAT SDK and DexScreener as optional source modules.

### Phase 8: Agent Orchestration

- Add prompts after schemas and risk decisions are stable.
- Bound memory to scrubbed research summaries.

## MVP Deferrals

- Live trading and withdrawals are permanently out of scope.
- Paid APIs, production monitoring, deployment automation, multi-user auth, and real-money portfolio accounting are beyond MVP.
- Testnet-specific adapters, Hummingbot MCP experiments, sentiment breadth, and multi-chain expansion wait until deterministic simulation is proven.

