# Dashboard

TRAIDR includes a local Streamlit command-center dashboard for operating TRAIDR without typing the underlying CLI commands. The dashboard now opens as a visual command center: chart first, intelligence stack beside it, daily mission guidance, safe workflow buttons, and DuckDB-backed evidence views.

## Run

Install dependencies, create a local fixture database, then start Streamlit:

```bash
python -m pip install -r requirements.txt
python scripts/run_simulation.py --database data/traidr.duckdb
python -m cli.main scan --fixture --database data/traidr.duckdb
python -m streamlit run dashboard/app.py
```

The CLI dashboard command prints the safe launch command instead of opening a UI automatically:

```bash
python -m cli.main dashboard
```

## Command Center Layout

- `Cockpit`: Bitunix public-data chart, intelligence stack, daily mission, and command strip.
- `Operations`: full safe action launcher, database summary, and setup guidance.
- `Radar`: risk-first candidate ranking and scan evidence.
- `Token Detail`: local token evidence, technical vectors, and anti-rug status.
- `Watchlist`: local watched pairs.
- `Portfolio`: manual positions, advisory risk decisions, paper orders/fills.
- `Alerts`: local alert history.
- `Reports`: local research reports.
- `Safety`: explicit non-execution posture.

Risk tables are shown before opportunity tables where both are present.

## Command Center Buttons

The dashboard includes buttons for:

- Run Daily Workflow
- Run Fixture Scan
- Run Paper Simulation
- Generate Test Alerts
- Run Scheduler Once
- Inspect DB / Status
- Check Status

These buttons call TRAIDR's Python command functions directly. They do not spawn shell commands, they do not expose arbitrary command execution, and each action result is summarized before the raw local output is tucked behind an expander.

## Bitunix Futures

The `Bitunix Futures` tab loads public Bitunix futures market data on button press and renders a native Lightweight Charts canvas with TRAIDR overlays. It does not iframe Bitunix and it does not provide order-entry controls. See `docs/bitunix_cockpit.md`.

The cockpit has a right-side intelligence stack for market state, opportunity, risk, liquidity/depth imbalance, funding state, and next safe action. The next safe action is always research-only and never becomes an exchange order.

## Missing Database

If the configured database is missing, the dashboard shows setup instructions. Running a Command Center button such as Daily Workflow, Fixture Scan, or Paper Simulation can create the local DuckDB file with research or paper-simulation records.

## Safety Boundary

The dashboard has no live trade, exchange order, withdrawal, signing, private-key, or live-execution controls. Button actions are allowlisted local workflows only. Research rows include `can_execute_trades: false` where relevant, and paper simulation remains risk-gated simulation only.
