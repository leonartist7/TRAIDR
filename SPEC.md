# TRAIDR v3.1 Product Specification

## System Objective

Project TRAIDR v3.1 is a local, simulation-first autonomous micro-cap crypto intelligence and paper-trading research engine. It gathers permitted market and on-chain observations, converts validated observations into deterministic technical and safety vectors, lets bounded agents produce research intents, and routes every actionable intent through deterministic validation before a simulated order can be recorded.

The MVP exists to research decision quality and safety behavior under scarce, noisy, and adversarial data. It is not a live trading system.

## Core Guarantees

- The default runtime mode is `simulation`.
- The starting bankroll is `$50` of simulated capital.
- MVP uses no paid APIs.
- Live trade execution is prohibited.
- Withdrawal flows are prohibited.
- Private keys, wallet seed phrases, exchange credentials, and API secrets are never exposed to LLM prompts or agent memory.
- An LLM may propose research observations or `BUY`, `SELL`, and `HOLD` intents, but it may not execute orders.
- The deterministic risk engine is final authority before any simulation or testnet execution path.
- `HOLD` is the default decision.
- `INSUFFICIENT_DATA` is the required outcome when input data is missing, stale, malformed, contradictory, or uncertain.
- Anti-rug hard-fail rules override bullish sentiment, technical momentum, and LLM output.

## Scope

### MVP In Scope

- Local Python 3.11 project structure.
- Simulation-only paper broker with `$50` initial cash.
- DuckDB local persistence for observations, vectors, intents, risk decisions, simulated fills, and audit events.
- Deterministic configuration loading and validation.
- Deterministic risk validation with anti-rug hard failures.
- Technical vector generation from validated snapshots.
- Free data-source adapter interfaces and safe optional adapters for DexScreener and GOAT SDK data access where feasible.
- Agent orchestration that returns bounded intents and TOON-compressed LLM payloads.
- Test coverage for simulation, safety invariants, storage, and data failure behavior.

### Out of Scope

- Live trading, live order signing, and live exchange or DEX execution.
- Withdrawals, transfers, bridging, custody, private-key management, or wallet recovery.
- Paid data feeds for MVP.
- Profit guarantees, financial advice, unattended real-money operation, and production custody.
- Any execution path where an LLM talks directly to an order API.

## Architecture

```text
free data adapters
       |
       v
data_pipeline validation ----> storage audit trail
       |
       v
technical vector engine ----> anti-rug observations
       |
       v
agent orchestration with TOON payloads
       |
       v
bounded intent: HOLD | BUY | SELL | INSUFFICIENT_DATA
       |
       v
deterministic risk engine
       |
       +----> reject / HOLD / INSUFFICIENT_DATA
       |
       v
simulation broker only
       |
       v
DuckDB portfolio, fills, and decision audit
```

Data collection, agent reasoning, risk validation, and execution are separate boundaries. Adapters supply data but do not decide trades. Agents produce intents but do not bypass risk. The simulation broker records fills but does not own safety policy.

## Safety Model

Safety is enforced by deterministic code and explicit data contracts:

1. Data validators reject stale, malformed, low-confidence, or missing fields before vectors are trusted.
2. Anti-rug checks run before bullish scoring or simulated order approval.
3. Agent output is parsed into a narrow intent schema. Invalid output becomes `INSUFFICIENT_DATA` or `HOLD`.
4. Risk validation rechecks mode, bankroll, notional limits, exposure, anti-rug status, and data freshness.
5. The execution boundary accepts only risk-approved simulation instructions. It must not accept raw agent output.
6. Audit records preserve source metadata, timestamps, reason codes, rejected intents, and simulated fills.

## Planned Modules

| Folder | Responsibility |
| --- | --- |
| `config/` | Simulation defaults, risk limits, source policies, and validated settings. |
| `data_pipeline/` | Snapshot contracts, freshness checks, normalization, provenance, and adapter ingestion. |
| `agents/` | Intent schemas, orchestrator, bounded research agents, and LLM gateway boundary. |
| `onchain/` | On-chain safety observations and optional safe SDK adapter wrappers. |
| `execution/` | Simulation broker, portfolio ledger, and future testnet-only boundary. |
| `risk/` | Deterministic risk decisions, anti-rug hard fails, exposure limits, and reason codes. |
| `prompts/` | Prompt templates that avoid secrets and request schema-bounded responses. |
| `sentiment/` | Sentiment contracts and optional free-source feature extraction. |
| `technicals/` | Technical vector building and indicator calculations. |
| `storage/` | DuckDB connection, schema migrations, repositories, and audit writers. |
| `utils/` | Time, validation, logging, TOON serialization, and shared result helpers. |
| `memory/` | Local research memory with bounded, scrubbed records. |
| `scripts/` | Local bootstrap, simulation run, and diagnostics entry points. |
| `tests/` | Unit, integration, safety, and simulation tests. |
| `docs/` | Architecture notes, decisions, runbooks, and safety documentation. |

## Planned File Tree

```text
.
|-- README.md
|-- SPEC.md
|-- AGENTS.md
|-- BUILD_PHASES.md
|-- SAFETY_RULES.md
|-- IMPLEMENTATION_PLAN.md
|-- TASK_GRAPH.md
|-- FILE_CHECKLIST.md
|-- MVP_CUTLINE.md
|-- TEST_PLAN.md
|-- pyproject.toml
|-- config/
|   |-- __init__.py
|   |-- settings.yaml
|   |-- risk.yaml
|   `-- logging.yaml
|-- data_pipeline/
|   |-- __init__.py
|   |-- contracts.py
|   |-- validation.py
|   |-- normalization.py
|   |-- dexscreener_adapter.py
|   `-- source_registry.py
|-- agents/
|   |-- __init__.py
|   |-- intents.py
|   |-- orchestrator.py
|   |-- llm_gateway.py
|   `-- research_agent.py
|-- onchain/
|   |-- __init__.py
|   |-- contracts.py
|   |-- rug_observations.py
|   `-- goat_adapter.py
|-- execution/
|   |-- __init__.py
|   |-- models.py
|   |-- simulation_broker.py
|   |-- portfolio_state.py
|   `-- testnet_boundary.py
|-- risk/
|   |-- __init__.py
|   |-- models.py
|   |-- anti_rug.py
|   |-- limits.py
|   `-- engine.py
|-- prompts/
|   |-- system_research.md
|   `-- intent_schema.md
|-- sentiment/
|   |-- __init__.py
|   |-- contracts.py
|   `-- features.py
|-- technicals/
|   |-- __init__.py
|   |-- indicators.py
|   `-- vector_engine.py
|-- storage/
|   |-- __init__.py
|   |-- duckdb_store.py
|   |-- schema.py
|   `-- repositories.py
|-- utils/
|   |-- __init__.py
|   |-- clocks.py
|   |-- logging.py
|   |-- results.py
|   `-- toon.py
|-- memory/
|   |-- __init__.py
|   `-- research_memory.py
|-- scripts/
|   |-- run_simulation.py
|   `-- inspect_db.py
|-- docs/
|   |-- architecture.md
|   |-- safety.md
|   `-- decisions.md
`-- tests/
    |-- unit/
    |   |-- test_risk_engine.py
    |   |-- test_anti_rug.py
    |   |-- test_vector_engine.py
    |   `-- test_toon.py
    |-- integration/
    |   |-- test_storage_flow.py
    |   `-- test_simulation_flow.py
    |-- safety/
    |   |-- test_no_live_trading.py
    |   |-- test_no_secret_payloads.py
    |   `-- test_insufficient_data.py
    `-- conftest.py
```

The listed runtime files are future implementation targets. This planning pass creates only the root Markdown documents.

## Operating Modes

| Mode | MVP Status | Behavior |
| --- | --- | --- |
| `simulation` | Required default | Uses simulated cash and simulated fills only. |
| `testnet` | Optional later | Must still pass deterministic risk and may only target explicitly safe testnet adapters. |
| `live` | Forbidden | Must not be implemented or selectable. |

## Risk Limits

The first implementation should encode conservative defaults and make them testable:

| Limit | MVP Default |
| --- | --- |
| Starting simulated cash | `$50.00` |
| Default action | `HOLD` |
| Maximum open positions | `3` |
| Maximum per-position simulated notional | `$5.00` |
| Maximum total simulated asset exposure | `$15.00` |
| Maximum new entry when data is stale or uncertain | `$0.00` |
| Maximum buy when anti-rug hard fail exists | `$0.00` |
| Maximum live-trade notional | `$0.00` |
| Withdrawal notional | `$0.00` |

These are research limits, not trading advice. A later config phase may make them configurable while preserving safe defaults and hard prohibitions.

## Technical Vector Strategy

The technical vector engine should produce deterministic, timestamped feature vectors from validated market snapshots. Vectors must carry freshness and provenance metadata and should avoid silently imputing missing values.

MVP vector candidates:

- Pair identity, chain identity, quote asset, source, and observation timestamp.
- Price change over supported windows if source data is fresh.
- Volume and liquidity summaries with quality flags.
- Transaction-count or buy/sell imbalance features when supplied by validated adapters.
- Volatility and momentum indicators only when sufficient observations exist.
- Anti-rug observation flags separated from bullish scoring inputs.
- Sentiment features only when a free source and confidence contract exist.

Vector policy:

- Missing required fields produce `INSUFFICIENT_DATA`.
- Stale observations produce `INSUFFICIENT_DATA`.
- Malformed numeric values produce `INSUFFICIENT_DATA`.
- Unknown feature confidence is carried forward as uncertainty, not optimism.
- TOON is used to compress safe LLM payloads; payloads contain summaries, reason codes, and scrubbed metadata rather than secrets or raw credentials.

## Anti-Rug Hard-Fail Rules

Anti-rug checks are vetoes. A veto blocks simulated `BUY` regardless of momentum or agent enthusiasm.

The MVP should hard fail when validated evidence indicates any of the following:

- Liquidity is absent, inaccessible, or below the configured safety floor for the requested entry.
- Liquidity lock or pool status is required by policy but unknown or fails validation.
- Token minting, freezing, blacklisting, transfer blocking, or sell restriction signals violate policy.
- Holder concentration or creator control crosses configured hard-fail thresholds when reliable holder data is available.
- Honeypot, tax, route, or sellability evidence indicates exit behavior is unsafe.
- Contract identity, pair identity, chain identity, or source provenance is ambiguous.
- Required anti-rug evidence is missing, stale, malformed, or uncertain.

`SELL` intents may be evaluated separately for simulated risk reduction, but must still use deterministic validation and valid portfolio state.

## Data and Storage

- DuckDB is the local system of record.
- Storage persists raw-source metadata where safe, normalized snapshots, technical vectors, intents, risk decisions, simulated orders, simulated fills, portfolio snapshots, and audit events.
- Stored LLM payloads must be scrubbed and bounded.
- No secret-bearing environment variable, credential file, private key, seed phrase, signing payload, or withdrawal instruction may enter DuckDB or prompt memory.

## Adapter Policy

- MVP adapters must work without paid APIs.
- DexScreener and GOAT SDK support are optional safe data-source modules, not mandatory order paths.
- Hummingbot MCP is optional and must be limited to simulation or explicit testnet mode.
- Adapters must return normalized results with timestamps, source identity, confidence/failure states, and no authority to execute trades.

## Decision Lifecycle

1. Collect free-source observations.
2. Normalize and validate data.
3. Persist evidence and failure reasons.
4. Build a deterministic vector or return `INSUFFICIENT_DATA`.
5. Build a TOON-compressed, scrubbed research payload.
6. Parse agent output into a bounded intent.
7. Apply anti-rug vetoes and risk limits.
8. Record `HOLD`, rejection, or a risk-approved simulated broker action.
9. Persist portfolio and audit state.

## Non-Functional Requirements

- Local-first operation with deterministic safety behavior.
- Clear reason codes for rejected actions.
- Small interfaces that allow adapters and agents to be tested without network access.
- Fail-closed behavior for parsing, validation, storage corruption, mode confusion, and data freshness uncertainty.
- Testable module boundaries that keep risk and simulation logic independent from LLM prompts.
