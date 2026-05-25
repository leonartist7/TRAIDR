# Ask TRAIDR

Ask TRAIDR is a local question interface over DuckDB summaries. It does not require an external LLM and cannot execute trades.

## Commands

```bash
python -m cli.main ask "what are my top risks?"
python -m cli.main ask "show best radar candidates"
python -m cli.main ask "what should I watch today?"
python -m cli.main ask "show recent alerts"
python -m cli.main ask "show portfolio summary"
python -m cli.main ask "show safety status"
python -m cli.main ask "show scan summary"
```

Use a specific local database:

```bash
python -m cli.main ask "show recent alerts" --database storage/duckdb/traidr.duckdb
```

## Supported Intents

- `top_risks`
- `top_opportunities`
- `recent_alerts`
- `portfolio_summary`
- `safety_status`
- `scan_summary`
- `unknown_question`

Unknown questions return suggestions instead of inventing an answer.

## Safety Boundary

- No LLM is required.
- No paid APIs are required.
- No execution actions are produced.
- Every answer includes `can_execute_trades: false`.
