# Build Phases

## Phase 0: Bootstrap

Purpose: establish the Python 3.11 project skeleton and developer tooling without implementing decision logic.

Deliverables:

- `pyproject.toml`
- Package directories with minimal `__init__.py` files where needed
- Test directory layout
- Local run/test conventions

Exit criteria:

- The repository imports cleanly where packages exist.
- `pytest` is wired for future tests.
- No live trading, credential, config, or adapter behavior is introduced early.

## Phase 1: Configs

Purpose: define safe defaults and validated settings.

Deliverables:

- Simulation mode defaults
- `$50` simulated capital default
- Risk limit settings
- Data freshness and source policy settings

Exit criteria:

- Invalid or forbidden mode selection fails closed.
- No setting enables live trading or withdrawals.

## Phase 2: Core Utilities

Purpose: create shared deterministic helpers.

Deliverables:

- Clock and freshness helpers
- Result and reason-code helpers
- Structured logging helpers
- TOON serialization boundary for scrubbed LLM payloads

Exit criteria:

- Utilities are testable without external services.
- Secret-like values are rejected or scrubbed at payload boundaries.

## Phase 3: Storage

Purpose: make DuckDB the local audit and research store.

Deliverables:

- DuckDB connection management
- Schema initialization
- Repositories for evidence, vectors, intents, risk decisions, and simulated fills

Exit criteria:

- Storage tests verify inserts, reads, and audit fields.
- Storage never requires a paid service or secret.

## Phase 4: Risk Engine

Purpose: implement deterministic final authority.

Deliverables:

- Intent and decision models
- Anti-rug veto checks
- Position, exposure, data freshness, and mode limits
- Fail-closed reason codes

Exit criteria:

- A bullish intent with a hard-fail risk flag cannot become a simulated buy.
- Missing or uncertain required data becomes `INSUFFICIENT_DATA`.
- Live and withdrawal actions are rejected by design.

## Phase 5: Simulation Broker

Purpose: record risk-approved paper actions only.

Deliverables:

- Simulated portfolio ledger
- Simulated orders and fills
- Cash and exposure accounting from `$50`

Exit criteria:

- Broker rejects unapproved instructions.
- Broker never reaches any live order path.

## Phase 6: Technical Vector Engine

Purpose: derive deterministic research features from validated snapshots.

Deliverables:

- Indicator helpers
- Vector builder
- Feature quality and provenance fields

Exit criteria:

- Insufficient lookback or bad fields fail closed.
- Vectors are deterministic for fixed input snapshots.

## Phase 7: Data Adapters

Purpose: add safe free-source inputs.

Deliverables:

- Adapter contracts and source registry
- DexScreener adapter if free access is appropriate
- GOAT SDK data adapter only as a safe optional module
- On-chain anti-rug observation interfaces

Exit criteria:

- Adapters normalize timestamps and failure states.
- Adapters cannot execute trades.
- Tests can replace network calls with fixtures.

## Phase 8: Agent Orchestration

Purpose: produce bounded research intents without execution authority.

Deliverables:

- Intent schema parsing
- TOON-compressed scrubbed prompt payloads
- Research orchestration with `HOLD` fallback
- Optional Hummingbot MCP boundary limited to simulation or testnet research workflows

Exit criteria:

- Invalid agent output cannot become an execution instruction.
- No secret reaches prompts or stored memory.

## Phase 9: Tests

Purpose: close safety gaps across modules.

Deliverables:

- Unit tests
- Integration tests
- Safety regression tests
- Simulation scenario tests

Exit criteria:

- `pytest` covers fail-closed behavior and main paper-trading flow.
- Regressions for forbidden capabilities are explicit.

## Phase 10: README and Docs

Purpose: document operation, safety boundaries, and architecture.

Deliverables:

- Setup and local run instructions
- Architecture docs
- Safety docs
- Decision notes and troubleshooting

Exit criteria:

- A new contributor can identify what is simulated, what is forbidden, and which phase comes next.

