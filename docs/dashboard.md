# Dashboard

TRAIDR includes a local Streamlit dashboard for read-only inspection of the DuckDB simulation database.

## Run

Install dependencies, create a local fixture database, then start Streamlit:

```bash
python -m pip install -r requirements.txt
python scripts/run_simulation.py --database data/traidr.duckdb
python -m streamlit run dashboard/app.py
```

## What It Shows

- Latest market evidence snapshots from `evidence_snapshots`.
- Technical vectors from `technical_vectors`.
- Anti-rug related evidence rows when present.
- Risk decisions from `risk_decisions`.
- Simulated orders and fills.
- Audit events.
- Static safety status from `config/settings.yaml`.

## Safety Boundary

The dashboard opens DuckDB in read-only mode and contains no trade, order, withdrawal, signing, private-key, or live-execution controls. If the configured database is missing, it shows setup instructions instead of creating or mutating storage.
