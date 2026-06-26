# TRAIDR

TRAIDR v3.1 is a local, simulation-first micro-cap crypto intelligence and paper-trading research engine. The MVP combines fixture-first observations, deterministic technical vectors, bounded mock agent research, DuckDB audit storage, and a deterministic risk gate before any paper action is recorded.

The current research layer also includes a personal market intelligence system: macro/news scoring, multi-agent CIO recommendations, ranked opportunity radar states, local alert history, and deterministic scheduler primitives. These outputs are recommendation-only and persisted locally in DuckDB.

## Safety Warning

This project is for simulation and research. It is not financial advice and must not be used as a live-trading or custody system.

Hard constraints:

- No live trades.
- No withdrawals.
- No private-key or seed phrase access.
- No secret exposure to LLM prompts or memory.
- No direct LLM order execution.
- Anti-rug hard fails override bullish signals.

## Simulation-Only Guarantee

The MVP defaults to simulation mode with `$50` of simulated capital. `HOLD` is the default decision. Missing, stale, malformed, contradictory, or uncertain required data must produce `INSUFFICIENT_DATA`.

Every future `BUY` or `SELL` intent must pass deterministic risk validation before it reaches a simulation broker. Optional GOAT SDK, DexScreener, or Hummingbot MCP work must preserve that boundary; Hummingbot use is limited to simulation or explicit testnet research.

## Setup

Use Python 3.11 for the target runtime.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Run Simulation

Run one offline fixture simulation. It uses in-memory DuckDB by default and never calls a network API.

```bash
python scripts/run_simulation.py
```

To write the fixture paper records to the configured local DuckDB path and inspect them:

```bash
python scripts/run_simulation.py --database data/traidr.duckdb
python scripts/inspect_db.py
```

## CLI

Install the local command center:

```bash
python -m pip install -e .
```

Examples:

```bash
traidr status
traidr simulate
traidr inspect
traidr radar
traidr report --type daily
traidr alerts
traidr alerts rules
traidr scan --fixture
traidr discover --fixture
traidr token --fixture
traidr briefing
traidr daily-run
traidr ask "what are my top risks?"
traidr news --fixture
traidr macro --fixture
traidr watch list
traidr portfolio report
traidr dashboard
traidr scheduler-once
```

`traidr dashboard` prints the Streamlit launch command instead of opening it automatically. See `docs/cli.md`.

CLI commands accept `--database` before or after the subcommand:

```bash
traidr inspect --database storage/duckdb/traidr_test.duckdb
```

## Dashboard

Run the local dashboard:

```bash
python -m streamlit run dashboard/app.py
```

The dashboard opens as a visual Command Center. The first screen is the `Cockpit`: a native Bitunix public-data chart, an intelligence stack, a daily mission checklist, and safe local workflow buttons. The `Operations` tab contains the fuller command launcher for Daily Workflow, Fixture Scan, Paper Simulation, Generate Alerts, Scheduler Once, and Status/Inspect DB.

Dashboard buttons run allowlisted local Python actions. They do not live trade, withdraw, access secrets, or execute arbitrary terminal commands.

See `docs/dashboard.md` for details.

The `Cockpit` uses public Bitunix futures market data for tickers, klines, funding, and depth, then renders TRAIDR's own chart, overlays, and research-only opportunity/risk panels. It does not iframe Bitunix and it has no order buttons. See `docs/bitunix_cockpit.md`.

## Ask TRAIDR

Ask local questions against DuckDB summaries without an external LLM:

```bash
python -m cli.main ask "what are my top risks?"
python -m cli.main ask "show best radar candidates"
python -m cli.main ask "what should I watch today?"
python -m cli.main ask "show recent alerts"
```

Ask TRAIDR is read-only and returns suggestions for unsupported questions. See `docs/ask_traidr.md`.

## Market Intelligence

TRAIDR can score local macro/news fixtures, combine structured non-executing agent analyses, rank watchlist opportunities, record local alert history, and run deterministic scheduler ticks from Python modules. The scheduler is intentionally a callable local research primitive, not a hidden daemon.

Key modules:

- `intelligence/` for macro regime, news scoring, and event calendar abstractions.
- `radar/` for watchlist ranking and opportunity states.
- `notifications/` for local alert history and optional injected ntfy, Telegram, or Discord transports.
- `scheduler/` for deterministic `1m`, `5m`, `15m`, `1h`, `4h`, and daily research task intervals.

See `docs/market_intelligence.md`, `docs/notifications.md`, and `docs/scheduler.md`.

Read-only macro and news adapters can be run in fixture mode or optional RSS/source mode:

```bash
python -m cli.main news --fixture
python -m cli.main macro --fixture
python -m cli.main news --source rss
python -m cli.main macro
```

Source failures return `INSUFFICIENT_DATA`; missing news is never treated as bullish. See `docs/news_macro_sources.md`.

## Sentiment And Smart Wallet Lite

TRAIDR includes local sentiment-lite feature extraction and fixture wallet-history scoring for personal research:

- Sentiment detects momentum, warnings, scam language, spam/shill repetition, and ticker mentions.
- Spam and scam language reduce confidence.
- Missing sentiment is neutral/insufficient, never bullish.
- Smart wallet scoring uses fixture wallet histories and graph evidence only.
- Unknown wallet history does not create bullish evidence.

See `docs/sentiment_lite.md` and `docs/smart_wallet_lite.md`.

## Scoring And Lifecycle

TRAIDR includes deterministic opportunity score v2 and candidate lifecycle tracking:

- Scoring combines liquidity, volume, technicals, safety, optional wallet/sentiment/macro evidence, and data quality.
- High rug risk caps opportunity.
- Missing critical safety data caps confidence.
- Low liquidity caps risk-adjusted score.
- Lifecycle events track discovered, watch, alert, review, stale, avoid, exit-risk, repeated appearance, risk increase, and liquidity changes.

These are research-only layers and cannot execute trades. See `docs/scoring_model.md` and `docs/lifecycle.md`.

## Research Thesis Notes

TRAIDR can generate structured research thesis notes for radar candidates:

- thesis summary
- opportunity drivers
- risk factors
- invalidation conditions
- watch conditions
- exit warning conditions
- confidence and data gaps

The thesis generator is not financial advice, does not execute trades, and always includes risk and invalidation notes. See `docs/thesis.md`.

## Market Scan

Run read-only fixture market scan and radar conversion:

```bash
python -m cli.main scan --fixture
python -m cli.main scan --fixture --database storage/duckdb/traidr_test.duckdb
python -m cli.main scan --source dexscreener --pair-ref solana/PAIR_ADDRESS
python -m cli.main radar --database storage/duckdb/traidr_test.duckdb
```

Real-source scan mode is optional and read-only. If data sources are unavailable or return no candidates, TRAIDR returns `INSUFFICIENT_DATA` or a clean no-candidates message rather than fabricating bullish data. See `docs/market_scan.md`.

## Token Discovery

Run offline discovery:

```bash
python -m cli.main discover --fixture
python -m cli.main discover --fixture --database storage/duckdb/traidr_discovery.duckdb
python -m cli.main discover --source dexscreener --limit 20
```

Discovery is research-only and cannot execute trades. See `docs/token_discovery.md`.

## Token Detail

Generate a read-only local token intelligence card:

```bash
python -m cli.main token --fixture
python -m cli.main token --pair-ref solana/PAIR_ADDRESS --source dexscreener
python -m cli.main token --pair-ref solana/PAIR_ADDRESS --source dexscreener --database storage/duckdb/traidr_token.duckdb
```

Token detail cards include market metrics, radar state, anti-rug evidence status, reason codes, and plain-English research notes. They are research-only and always include `can_execute_trades: False`. See `docs/token_detail.md`.

## Daily Briefing

Generate a read-only local daily intelligence briefing from DuckDB:

```bash
python -m cli.main briefing
python -m cli.main briefing --database storage/duckdb/traidr.duckdb
```

Briefings summarize market scan evidence, radar candidates, alerts, simulation results, safety status, missing data warnings, and suggested watchlists. They never create execution actions. See `docs/daily_briefing.md`.

## Daily Run

Run the local research workflow in one command:

```bash
python -m cli.main daily-run --database storage/duckdb/traidr.duckdb
```

The daily run performs a status check, read-only fixture scan, watchlist update when available, radar update, local alert generation, daily briefing, and DuckDB report persistence. It never executes trades. See `docs/daily_run.md`.

## Operator Notes

For day-to-day use, run commands one at a time against the same DuckDB file. DuckDB is local and file-backed, so a dashboard session or another terminal can hold a file lock while it is reading the database.

If a command reports a DuckDB file lock:

1. Close any dashboard or other terminal using the same database.
2. Rerun the command after the previous process exits.
3. Use a separate `--database storage/duckdb/<name>.duckdb` path for experiments.

The default daily workflow is fixture-first. Real-source commands are optional and read-only, and source failures return `INSUFFICIENT_DATA` instead of fabricated bullish data.

## Watchlist

Manage a local read-only watchlist in DuckDB:

```bash
python -m cli.main watch add solana/PAIR_ADDRESS --note "watch liquidity"
python -m cli.main watch list
python -m cli.main watch remove solana/PAIR_ADDRESS
python -m cli.main watch scan
```

`watch scan` uses read-only market data boundaries and can create local alerts when risk worsens or opportunity improves. It never creates execution actions. See `docs/watchlist.md`.

## Alert Rules

List alert rules or run a deterministic local alert test:

```bash
python -m cli.main alerts
python -m cli.main alerts rules
python -m cli.main alerts test
```

Alert rules generate local notification history from radar, watchlist, and scan changes. They are deduplicated and cannot execute trades. See `docs/alert_rules.md`.

## Manual Portfolio

Track local manual positions for personal analysis:

```bash
python -m cli.main portfolio add BONK --entry 0.001 --size-usd 20 --thesis "meme momentum"
python -m cli.main portfolio list
python -m cli.main portfolio remove <entry_id>
python -m cli.main portfolio report
python -m cli.main portfolio monitor
python -m cli.main portfolio sell-risk
```

Manual portfolio tracking does not connect to exchanges or wallets and cannot execute trades. See `docs/portfolio.md`.

The sell-risk monitor reviews manual positions against local evidence and returns research states such as `HOLD_POSITION`, `REVIEW_POSITION`, `REDUCE_RISK`, `EXIT_CANDIDATE`, or `INSUFFICIENT_DATA`. It never executes trades. See `docs/sell_risk.md`.

## Test

```bash
python -m pytest
```

## Optional Graphify Analysis

Graphify may be used as an optional dev-only repository analysis tool. It is not part of TRAIDR runtime dependencies and is scoped by `.graphifyignore` to avoid local environments, caches, storage artifacts, log output, DuckDB or Parquet files, and `.env` files.

See `docs/graphify.md` for the optional Codex and PowerShell workflow.

## Architecture Summary

TRAIDR uses explicit boundaries:

1. Free data adapters collect source observations.
2. The data pipeline validates freshness, shape, provenance, and confidence.
3. Technical and safety modules build deterministic vectors and anti-rug evidence.
4. Agents receive scrubbed TOON-compressed research payloads and return bounded intents.
5. The deterministic risk engine approves, rejects, or degrades decisions.
6. The simulation broker records paper-only portfolio changes in DuckDB.
7. Market intelligence modules persist recommendations, alerts, scheduler runs, and reports without execution authority.

See `SPEC.md`, `SAFETY_RULES.md`, and `IMPLEMENTATION_PLAN.md` before implementing runtime modules.

The MVP implementation is described further in `docs/architecture.md`, `docs/safety.md`, `docs/decisions.md`, `docs/OPERATOR_GUIDE.md`, and `docs/FINAL_PHASE_40_VERIFICATION.md`.

## Not Implemented

- Live trading, exchange order routing, and live market loops.
- Withdrawals, transfers, bridging, custody, signing, or private-key handling.
- Real LLM provider calls.
- Paid APIs or key-required source adapters.
- Background autonomous notification daemons.
- Notification secrets or tokens stored by TRAIDR.

## Next Roadmap

The next safe increments are richer fixture and adapter coverage, config loading for local operator settings, portfolio snapshots, and deeper research reporting while preserving the deterministic risk and simulation boundaries.
