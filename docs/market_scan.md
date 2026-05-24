# Market Scan

TRAIDR market scan mode is read-only research. It normalizes market data through existing safe adapter boundaries, maps scan candidates into the opportunity radar, and can store scan evidence in local DuckDB.

## Commands

Offline fixture scan:

```powershell
python -m cli.main scan --fixture
```

Persist fixture scan evidence:

```powershell
python -m cli.main scan --fixture --database storage/duckdb/traidr_test.duckdb
```

Optional real-source scan requires an explicit source and pair reference. DexScreener pair references use `<chain>/<pairAddress>`.

```powershell
python -m cli.main scan --source dexscreener --pair-ref solana/PAIR_ADDRESS
python -m cli.main scan --source dexscreener --pair-ref solana/PAIR_ADDRESS --database storage/duckdb/traidr_scan_test.duckdb
python -m cli.main radar --database storage/duckdb/traidr_scan_test.duckdb
```

If `--source` is omitted and `--fixture` is false, TRAIDR returns `INSUFFICIENT_DATA` with instructions. If DexScreener is unavailable, returns an HTTP error, or returns missing price/liquidity/volume fields, TRAIDR returns `INSUFFICIENT_DATA` rather than fabricating candidate data.

## Output Fields

Every scan candidate includes:

- token/pair id
- source
- observed timestamp
- price, liquidity, and 24h volume when available
- data-quality status
- reason codes
- `can_execute_trades: False`

## Safety

- Scan mode never executes trades.
- Scan mode never handles withdrawals.
- Scan mode never handles private keys or wallet signing.
- Real-source failures never fabricate bullish data.
- Missing or failed data returns `INSUFFICIENT_DATA`.
