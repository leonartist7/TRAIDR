# Dashboard

TRAIDR includes a local Streamlit command-center dashboard for read-only inspection of the DuckDB research database.

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

## Pages

- Market Radar
- Scan Evidence
- Token Detail
- Watchlist
- Portfolio
- Alerts
- Reports
- Safety Status

Risk tables are shown before opportunity tables where both are present.

## Missing Database

If the configured database is missing, the dashboard shows setup instructions. It does not create or mutate storage.

## Safety Boundary

The dashboard opens DuckDB in read-only mode and contains no trade, order, withdrawal, signing, private-key, or live-execution controls. Research rows include `can_execute_trades: false` where relevant.
