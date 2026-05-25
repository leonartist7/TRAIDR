# File Checklist

Status values are `not_started`, `partial`, or `complete`.

| Path | Purpose | MVP Required | Status |
| --- | --- | --- | --- |
| `README.md` | MVP overview, safety notice, and local commands | yes | complete |
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
| `config/settings.py` | Deferred post-MVP validated settings loader | no | not_started |
| `config/defaults.toml` | Deferred config-name variant; MVP uses YAML defaults | no | not_started |
| `config/risk_limits.toml` | Deferred config-name variant; MVP uses `config/risk.yaml` | no | not_started |
| `cli/__init__.py` | Operator CLI package marker | no | complete |
| `cli/main.py` | TRAIDR argparse command entry point | no | complete |
| `cli/commands.py` | Local command center implementations | no | complete |
| `cli/formatters.py` | Terminal output formatting helpers | no | complete |
| `data_pipeline/__init__.py` | Data pipeline package marker | yes | complete |
| `data_pipeline/contracts.py` | Snapshot and adapter contracts | yes | complete |
| `data_pipeline/validation.py` | Freshness and shape validation | yes | complete |
| `data_pipeline/normalization.py` | Source normalization helpers | yes | complete |
| `data_pipeline/source_registry.py` | Free-source adapter registry | yes | complete |
| `data_pipeline/dexscreener_adapter.py` | Optional DexScreener market adapter | no | complete |
| `data_pipeline/coingecko_adapter.py` | Optional read-only CoinGecko market adapter | no | complete |
| `data_pipeline/defillama_adapter.py` | Optional read-only DefiLlama market adapter | no | complete |
| `data_pipeline/live_market_loader.py` | Optional read-only market source loader | no | complete |
| `data_pipeline/market_scan.py` | Read-only market scan orchestration | no | complete |
| `data_pipeline/scan_models.py` | Market scan result models | no | complete |
| `data_pipeline/token_discovery.py` | Read-only token discovery orchestration | no | complete |
| `data_pipeline/discovery_models.py` | Token discovery result models | no | complete |
| `agents/__init__.py` | Agents package marker | yes | complete |
| `agents/intents.py` | Bounded intent models | yes | complete |
| `agents/orchestrator.py` | Research and risk routing | yes | complete |
| `agents/llm_gateway.py` | Scrubbed LLM boundary | yes | complete |
| `agents/research_agent.py` | Research intent producer | no | complete |
| `agents/macro_agent.py` | Structured macro context analysis agent | no | complete |
| `agents/news_agent.py` | Structured news context analysis agent | no | complete |
| `agents/onchain_agent.py` | Structured on-chain activity analysis agent | no | complete |
| `agents/token_safety_agent.py` | Structured token safety analysis agent | no | complete |
| `agents/technical_agent.py` | Structured technical analysis agent | no | complete |
| `agents/narrative_agent.py` | Structured narrative analysis agent | no | complete |
| `agents/liquidity_agent.py` | Structured liquidity analysis agent | no | complete |
| `agents/portfolio_risk_agent.py` | Structured portfolio risk analysis agent | no | complete |
| `agents/opportunity_ranker.py` | Multi-agent opportunity/risk ranker | no | complete |
| `agents/cio_agent.py` | CIO recommendation aggregator | no | complete |
| `agents/agent_bus.py` | Structured non-executing agent bus | no | complete |
| `intelligence/__init__.py` | Market intelligence package marker | no | complete |
| `intelligence/macro_regime.py` | Local macro regime risk-on/risk-off scoring | no | complete |
| `intelligence/news_scoring.py` | Fixture-first news scoring | no | complete |
| `intelligence/event_calendar.py` | Local event calendar abstraction | no | complete |
| `radar/__init__.py` | Opportunity radar package marker | no | complete |
| `radar/models.py` | Opportunity radar state models | no | complete |
| `radar/state_machine.py` | Opportunity state transitions | no | complete |
| `radar/watchlist.py` | Watchlist normalization helpers | no | complete |
| `radar/opportunity_radar.py` | Ranked opportunity radar | no | complete |
| `radar/scan_to_radar.py` | Convert scan candidates to radar rankings | no | complete |
| `radar/discovery_to_radar.py` | Convert discovery candidates to radar rankings | no | complete |
| `token_detail/__init__.py` | Token detail package marker | no | complete |
| `token_detail/detail_models.py` | Read-only token detail report models | no | complete |
| `token_detail/detail_builder.py` | Single-token intelligence card builder | no | complete |
| `token_detail/formatters.py` | Token detail terminal formatter | no | complete |
| `notifications/__init__.py` | Notification package marker | no | complete |
| `notifications/models.py` | Alert and send result models | no | complete |
| `notifications/history.py` | DuckDB-backed local alert history | no | complete |
| `notifications/dedupe.py` | Alert fingerprint deduplication | no | complete |
| `notifications/senders.py` | Optional injected notification sender boundaries | no | complete |
| `notifications/dispatcher.py` | Deduping notification dispatcher | no | complete |
| `reports/__init__.py` | Reports package marker | no | complete |
| `reports/report_models.py` | Read-only report state models | no | complete |
| `reports/daily_briefing.py` | DuckDB-backed daily intelligence briefing builder | no | complete |
| `reports/formatters.py` | Daily briefing terminal formatter | no | complete |
| `alerts/__init__.py` | Alert rules package marker | no | complete |
| `alerts/rules.py` | Research alert rule definitions | no | complete |
| `alerts/rule_engine.py` | Local alert rule evaluation and dispatch | no | complete |
| `alerts/alert_templates.py` | Research-only alert message templates | no | complete |
| `portfolio/__init__.py` | Manual portfolio package marker | no | complete |
| `portfolio/models.py` | Manual portfolio entry and report models | no | complete |
| `portfolio/repository.py` | DuckDB-backed manual portfolio repository | no | complete |
| `portfolio/service.py` | Manual portfolio service layer | no | complete |
| `portfolio/exposure.py` | Manual portfolio exposure analytics | no | complete |
| `watchlist/__init__.py` | Watchlist package marker | no | complete |
| `watchlist/models.py` | Local watchlist models | no | complete |
| `watchlist/repository.py` | DuckDB-backed watchlist repository | no | complete |
| `watchlist/service.py` | Read-only watchlist scan and alert service | no | complete |
| `scheduler/__init__.py` | Research scheduler package marker | no | complete |
| `scheduler/tasks.py` | Deterministic research task intervals | no | complete |
| `scheduler/research_scheduler.py` | Testable due-task runner | no | complete |
| `scheduler/reports.py` | Local research report summaries | no | complete |
| `onchain/__init__.py` | On-chain package marker | yes | complete |
| `onchain/contracts.py` | On-chain observation contracts | yes | complete |
| `onchain/rug_observations.py` | Anti-rug evidence helpers | yes | complete |
| `onchain/goat_adapter.py` | Optional GOAT SDK data adapter | no | complete |
| `onchain/lp_lock_analysis.py` | LP lock status anti-rug signal helper | no | complete |
| `onchain/holder_concentration.py` | Holder concentration anti-rug signal helper | no | complete |
| `onchain/static_contract_risk.py` | Optional static scanner JSON anti-rug mapper | no | complete |
| `onchain/wallet_cluster_flags.py` | Wallet cluster anti-rug signal helper | no | complete |
| `onchain/wallet_graph.py` | Fixture-only NetworkX wallet graph builder | no | complete |
| `onchain/wallet_cluster_scorer.py` | Wallet graph cluster risk scoring helper | no | complete |
| `execution/__init__.py` | Execution package marker | yes | complete |
| `execution/models.py` | Approved simulation instruction models | yes | complete |
| `execution/portfolio.py` | Deferred name variant; MVP ledger is `execution/portfolio_state.py` | no | not_started |
| `execution/portfolio_state.py` | Simulated cash and holdings state ledger | yes | complete |
| `execution/order_validator.py` | Risk-gated paper order validator | yes | complete |
| `execution/slippage.py` | Deterministic paper slippage and partial fills | yes | complete |
| `execution/liquidity_depth.py` | Simulation-only liquidity depth and size impact model | no | complete |
| `execution/gap_risk.py` | Simulation-only stop-loss gap risk model | no | complete |
| `execution/rug_crash_model.py` | Simulation-only liquidity drain and rug crash model | no | complete |
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
| `scripts/run_simulation.py` | Local simulation entry point | yes | complete |
| `scripts/inspect_db.py` | Local DuckDB inspection helper | no | complete |
| `docs/architecture.md` | Architecture notes | no | complete |
| `docs/safety.md` | Expanded safety documentation | no | complete |
| `docs/decisions.md` | Architecture decision notes | no | complete |
| `docs/final_mvp_audit.md` | Final MVP safety and readiness audit | yes | complete |
| `docs/STABILIZATION_REPORT.md` | Stabilization verification and deferral report | yes | complete |
| `docs/dashboard.md` | Read-only Streamlit dashboard usage | no | complete |
| `docs/cli.md` | Operator CLI usage and safety notes | no | complete |
| `docs/market_intelligence.md` | Personal market intelligence architecture | no | complete |
| `docs/market_scan.md` | Read-only market scan usage | no | complete |
| `docs/DEXSCREENER_SCAN_REPORT.md` | Read-only DexScreener scan report | no | complete |
| `docs/token_discovery.md` | Read-only token discovery usage | no | complete |
| `docs/token_detail.md` | Read-only token detail usage | no | complete |
| `docs/daily_briefing.md` | Daily briefing report usage | no | complete |
| `docs/watchlist.md` | Local watchlist usage and safety notes | no | complete |
| `docs/alert_rules.md` | Research alert rule usage and safety notes | no | complete |
| `docs/portfolio.md` | Manual portfolio tracker usage and safety notes | no | complete |
| `docs/notifications.md` | Local and optional notification boundaries | no | complete |
| `docs/scheduler.md` | Deterministic research scheduler notes | no | complete |
| `GRAPH_REPORT.md` | Optional configured Graphify audit report | no | not_started |
| `dashboard/app.py` | Read-only Streamlit dashboard entry point | no | complete |
| `dashboard/components.py` | Dashboard display components | no | complete |
| `dashboard/queries.py` | Read-only DuckDB dashboard queries | no | complete |
| `tests/conftest.py` | Shared test fixtures | yes | complete |
| `tests/unit/test_clocks.py` | Freshness fail-closed unit tests | yes | complete |
| `tests/unit/test_cli_commands.py` | Operator CLI command tests | no | complete |
| `tests/unit/test_data_validation.py` | Normalized source validation tests | yes | complete |
| `tests/unit/test_coingecko_adapter.py` | CoinGecko read-only adapter tests | no | complete |
| `tests/unit/test_defillama_adapter.py` | DefiLlama read-only adapter tests | no | complete |
| `tests/unit/test_dexscreener_real_shape.py` | DexScreener response-shape normalization tests | no | complete |
| `tests/unit/test_live_market_loader.py` | Optional market loader tests | no | complete |
| `tests/unit/test_market_scan.py` | Read-only market scan tests | no | complete |
| `tests/unit/test_token_discovery.py` | Read-only token discovery tests | no | complete |
| `tests/unit/test_token_detail.py` | Read-only token detail card tests | no | complete |
| `tests/unit/test_daily_briefing.py` | Daily briefing report tests | no | complete |
| `tests/unit/test_watchlist_service.py` | Watchlist service and alert tests | no | complete |
| `tests/unit/test_alert_rules_engine.py` | Research alert rule engine tests | no | complete |
| `tests/unit/test_portfolio_service.py` | Manual portfolio service tests | no | complete |
| `tests/unit/test_portfolio_exposure.py` | Manual portfolio exposure tests | no | complete |
| `tests/unit/test_scan_command_real_mode.py` | CLI real scan mode tests with mocked source | no | complete |
| `tests/unit/test_source_registry.py` | Safe source registry tests | yes | complete |
| `tests/unit/test_onchain_observations.py` | Anti-rug observation mapping tests | yes | complete |
| `tests/unit/test_lp_lock_analysis.py` | LP lock anti-rug signal tests | no | complete |
| `tests/unit/test_holder_concentration.py` | Holder concentration signal tests | no | complete |
| `tests/unit/test_static_contract_risk.py` | Static contract risk mapper tests | no | complete |
| `tests/unit/test_wallet_cluster_flags.py` | Wallet cluster signal tests | no | complete |
| `tests/unit/test_wallet_graph.py` | Fixture wallet graph tests | no | complete |
| `tests/unit/test_wallet_cluster_scorer.py` | Wallet graph scoring tests | no | complete |
| `tests/unit/test_intents.py` | Strict bounded intent parser tests | yes | complete |
| `tests/unit/test_agent_bus.py` | Multi-agent bus tests | no | complete |
| `tests/unit/test_opportunity_ranker.py` | Opportunity ranker tests | no | complete |
| `tests/unit/test_cio_agent.py` | CIO aggregation tests | no | complete |
| `tests/unit/test_macro_regime.py` | Macro regime scoring tests | no | complete |
| `tests/unit/test_news_scoring.py` | News scoring tests | no | complete |
| `tests/unit/test_event_calendar.py` | Event calendar freshness tests | no | complete |
| `tests/unit/test_opportunity_radar.py` | Radar state and ranking tests | no | complete |
| `tests/unit/test_scan_to_radar.py` | Scan-to-radar conversion tests | no | complete |
| `tests/unit/test_discovery_to_radar.py` | Discovery-to-radar conversion tests | no | complete |
| `tests/unit/test_notifications.py` | Notification dedupe and sender tests | no | complete |
| `tests/unit/test_scheduler.py` | Scheduler and report tests | no | complete |
| `tests/unit/test_llm_gateway.py` | Mock LLM gateway tests | yes | complete |
| `tests/unit/test_orchestrator.py` | Agent risk routing tests | yes | complete |
| `tests/unit/test_results.py` | Shared result object unit tests | yes | complete |
| `tests/unit/test_risk_engine.py` | Risk engine unit tests | yes | complete |
| `tests/unit/test_anti_rug.py` | Veto regression tests | yes | complete |
| `tests/unit/test_simulation_broker.py` | Paper broker unit tests | yes | complete |
| `tests/unit/test_liquidity_depth.py` | Liquidity depth model tests | no | complete |
| `tests/unit/test_gap_risk.py` | Gap risk model tests | no | complete |
| `tests/unit/test_rug_crash_model.py` | Rug crash model tests | no | complete |
| `tests/unit/test_trailing_stop.py` | Trailing stop unit tests | yes | complete |
| `tests/unit/test_take_profit.py` | Take-profit unit tests | yes | complete |
| `tests/unit/test_vector_engine.py` | Vector behavior tests | yes | complete |
| `tests/unit/test_toon.py` | Payload boundary tests | yes | complete |
| `tests/integration/test_storage_schema.py` | DuckDB schema initialization flow | yes | complete |
| `tests/integration/test_storage_flow.py` | DuckDB integration flow | yes | complete |
| `tests/integration/test_watchlist_storage.py` | Watchlist DuckDB persistence flow | no | complete |
| `tests/integration/test_portfolio_storage.py` | Manual portfolio DuckDB persistence flow | no | complete |
| `tests/integration/test_intelligence_persistence.py` | Intelligence DuckDB persistence flow | no | complete |
| `tests/integration/test_execution_flow.py` | Risk-gated execution integration flow | yes | complete |
| `tests/integration/test_simulation_flow.py` | Paper broker integration flow | yes | complete |
| `tests/safety/test_no_live_trading.py` | Forbidden execution regression tests | yes | complete |
| `tests/safety/test_no_secret_payloads.py` | Secret boundary regression tests | yes | complete |
| `tests/safety/test_insufficient_data.py` | Fail-closed data tests | yes | complete |
| `tests/safety/test_no_llm_direct_execution.py` | Raw LLM execution boundary tests | yes | complete |
| `tests/safety/test_anti_rug_overrides_bullish.py` | Anti-rug veto safety tests | yes | complete |
| `tests/safety/test_market_intelligence_no_execution.py` | Intelligence package no-execution import guard | no | complete |

## Stabilization Deferrals

- The MVP reads safe YAML config artifacts directly: `config/settings.yaml` and `config/risk.yaml`. A Python settings loader and TOML config-name variants remain post-MVP work.
- The implemented simulation ledger is `execution/portfolio_state.py`; `execution/portfolio.py` is not required for the MVP and stays deferred instead of duplicating the active ledger.
