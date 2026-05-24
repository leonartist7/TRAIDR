# TRAIDR CLI

The TRAIDR command center is a local-first terminal interface for daily research use. It never enables live trading, withdrawals, private-key handling, or AI direct execution.

## Install

From the repository root:

```powershell
python -m pip install -e .
```

Then use:

```powershell
traidr status
```

Without an editable install, run the module directly:

```powershell
python -m cli.main status
```

## Commands

```powershell
traidr status
traidr simulate
traidr inspect
traidr radar
traidr report --type 4h
traidr report --type daily
traidr alerts
traidr dashboard
traidr scheduler-once
```

## Safety

- `traidr simulate` runs the existing deterministic paper-simulation path.
- `traidr dashboard` prints the Streamlit launch command and does not auto-launch.
- `traidr radar`, `traidr report`, and `traidr alerts` read local DuckDB records or safe fixtures.
- `traidr scheduler-once` runs due local research tasks once and stores scheduler/report records in DuckDB.
- No command routes to exchange execution, withdrawal flows, wallet signing, or private-key handling.

## Database

Commands default to `config/settings.yaml`:

```text
data/traidr.duckdb
```

Use `--database` before the command to override:

```powershell
traidr --database C:\tmp\traidr.duckdb inspect
```
