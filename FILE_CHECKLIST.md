# File Checklist

Status values are `not_started`, `partial`, or `complete`.

| Path | Purpose | MVP Required | Status |
| --- | --- | --- | --- |
| `README.md` | Starter overview and safety notice | yes | complete |
| `SPEC.md` | Product specification | yes | complete |
| `AGENTS.md` | Codex repository instructions | yes | complete |
| `BUILD_PHASES.md` | Phase ordering | yes | complete |
| `SAFETY_RULES.md` | Hard safety rules | yes | complete |
| `IMPLEMENTATION_PLAN.md` | Phase-by-phase delivery plan | yes | complete |
| `TASK_GRAPH.md` | Dependencies and critical path | yes | complete |
| `FILE_CHECKLIST.md` | Planned file inventory | yes | complete |
| `MVP_CUTLINE.md` | Day-1 MVP boundary | yes | complete |
| `TEST_PLAN.md` | Test strategy | yes | complete |
| `.gitignore` | Local Python and Codex artifact ignores | yes | complete |
| `pyproject.toml` | Python 3.11 packaging and test metadata | yes | complete |
| `requirements.txt` | Bootstrap dependency list for local setup | yes | complete |
| `config/__init__.py` | Config package marker | yes | complete |
| `config/settings.yaml` | Safe simulation and storage defaults | yes | complete |
| `config/risk.yaml` | Deterministic risk and anti-rug policy defaults | yes | complete |
| `config/mcp_config.json` | Optional MCP safety boundary defaults | no | complete |
| `config/logging.yaml` | Safe logging configuration defaults | yes | complete |
| `config/scoring_weights.yaml` | Research-only scoring weights | no | complete |
| `config/wallet_filters.yaml` | On-chain observation filter defaults | no | complete |
| `config/data_sources.yaml` | Free-source and fixture source policy | yes | complete |
| `config/exchanges.yaml` | Paper broker target policy | yes | complete |
| `config/settings.py` | Validated settings loader | yes | not_started |
| `config/defaults.toml` | Safe simulation defaults | yes | not_started |
| `config/risk_limits.toml` | Editable risk limit defaults | yes | not_started |
| `data_pipeline/__init__.py` | Data pipeline package marker | yes | complete |
| `data_pipeline/contracts.py` | Snapshot and adapter contracts | yes | complete |
| `data_pipeline/validation.py` | Freshness and shape validation | yes | complete |
| `data_pipeline/normalization.py` | Source normalization helpers | yes | complete |
| `data_pipeline/source_registry.py` | Free-source adapter registry | yes | complete |
| `data_pipeline/dexscreener_adapter.py` | Optional DexScreener market adapter | no | complete |
| `agents/__init__.py` | Agents package marker | yes | complete |
| `agents/intents.py` | Bounded intent models | yes | complete |
| `agents/orchestrator.py` | Research and risk routing | yes | complete |
| `agents/llm_gateway.py` | Scrubbed LLM boundary | yes | complete |
| `agents/research_agent.py` | Research intent producer | no | complete |
| `onchain/__init__.py` | On-chain package marker | yes | complete |
| `onchain/contracts.py` | On-chain observation contracts | yes | complete |
| `onchain/rug_observations.py` | Anti-rug evidence helpers | yes | complete |
| `onchain/goat_adapter.py` | Optional GOAT SDK data adapter | no | complete |
| `execution/__init__.py` | Execution package marker | yes | complete |
| `execution/models.py` | Approved simulation instruction models | yes | complete |
| `execution/portfolio.py` | Simulated cash and holdings ledger | yes | not_started |
| `execution/portfolio_state.py` | Simulated cash and holdings state ledger | yes | complete |
| `execution/order_validator.py` | Risk-gated paper order validator | yes | complete |
| `execution/slippage.py` | Deterministic paper slippage and partial fills | yes | complete |
| `execution/trailing_stop.py` | Five percent simulated trailing stop | yes | complete |
| `execution/take_profit.py` | Twenty percent simulated take-profit target | yes | complete |
| `execution/audit.py` | Simulation execution audit bridge | yes | complete |
| `execution/execution_daemon.py` | Simulation execution coordinator | yes | complete |
| `execution/simulation_broker.py` | Paper broker | yes | complete |
| `execution/testnet_boundary.py` | Later testnet-only boundary | no | not_started |
| `risk/__init__.py` | Risk package marker | yes | complete |
| `risk/models.py` | Risk input and decision models | yes | complete |
| `risk/anti_rug.py` | Anti-rug veto checks | yes | complete |
| `risk/limits.py` | Exposure and bankroll limits | yes | complete |
| `risk/engine.py` | Final deterministic validator | yes | complete |
| `prompts/master_system_prompt.md` | Bounded research system prompt | yes | complete |
| `prompts/output_schema.json` | Research output schema | yes | complete |
| `prompts/system_research.md` | Safe system prompt template | no | complete |
| `prompts/intent_schema.md` | Bounded intent response instructions | no | complete |
| `sentiment/__init__.py` | Sentiment package marker | no | complete |
| `sentiment/contracts.py` | Sentiment feature contracts | no | not_started |
| `sentiment/features.py` | Optional free sentiment features | no | not_started |
| `technicals/__init__.py` | Technicals package marker | yes | complete |
| `technicals/indicators.py` | Deterministic indicators | yes | complete |
| `technicals/vector_engine.py` | Feature vector builder | yes | complete |
| `storage/__init__.py` | Storage package marker | yes | complete |
| `storage/duckdb_store.py` | DuckDB lifecycle helpers | yes | complete |
| `storage/schema.py` | Local schema initialization | yes | complete |
| `storage/repositories.py` | Audit and research repositories | yes | complete |
| `utils/__init__.py` | Utilities package marker | yes | complete |
| `utils/clocks.py` | Clock and freshness helpers | yes | complete |
| `utils/logging.py` | Safe structured logging | yes | complete |
| `utils/results.py` | Result and reason-code helpers | yes | complete |
| `utils/toon.py` | TOON payload boundary | yes | complete |
| `memory/__init__.py` | Memory package marker | no | complete |
| `memory/research_memory.py` | Scrubbed research memory | no | complete |
| `scripts/run_simulation.py` | Local simulation entry point | yes | not_started |
| `scripts/inspect_db.py` | Local DuckDB inspection helper | no | not_started |
| `docs/architecture.md` | Architecture notes | no | not_started |
| `docs/safety.md` | Expanded safety documentation | no | not_started |
| `docs/decisions.md` | Architecture decision notes | no | not_started |
| `tests/conftest.py` | Shared test fixtures | yes | not_started |
| `tests/unit/test_clocks.py` | Freshness fail-closed unit tests | yes | complete |
| `tests/unit/test_data_validation.py` | Normalized source validation tests | yes | complete |
| `tests/unit/test_source_registry.py` | Safe source registry tests | yes | complete |
| `tests/unit/test_onchain_observations.py` | Anti-rug observation mapping tests | yes | complete |
| `tests/unit/test_intents.py` | Strict bounded intent parser tests | yes | complete |
| `tests/unit/test_llm_gateway.py` | Mock LLM gateway tests | yes | complete |
| `tests/unit/test_orchestrator.py` | Agent risk routing tests | yes | complete |
| `tests/unit/test_results.py` | Shared result object unit tests | yes | complete |
| `tests/unit/test_risk_engine.py` | Risk engine unit tests | yes | complete |
| `tests/unit/test_anti_rug.py` | Veto regression tests | yes | complete |
| `tests/unit/test_simulation_broker.py` | Paper broker unit tests | yes | complete |
| `tests/unit/test_trailing_stop.py` | Trailing stop unit tests | yes | complete |
| `tests/unit/test_take_profit.py` | Take-profit unit tests | yes | complete |
| `tests/unit/test_vector_engine.py` | Vector behavior tests | yes | complete |
| `tests/unit/test_toon.py` | Payload boundary tests | yes | complete |
| `tests/integration/test_storage_schema.py` | DuckDB schema initialization flow | yes | complete |
| `tests/integration/test_storage_flow.py` | DuckDB integration flow | yes | complete |
| `tests/integration/test_execution_flow.py` | Risk-gated execution integration flow | yes | complete |
| `tests/integration/test_simulation_flow.py` | Paper broker integration flow | yes | not_started |
| `tests/safety/test_no_live_trading.py` | Forbidden execution regression tests | yes | not_started |
| `tests/safety/test_no_secret_payloads.py` | Secret boundary regression tests | yes | complete |
| `tests/safety/test_insufficient_data.py` | Fail-closed data tests | yes | complete |
