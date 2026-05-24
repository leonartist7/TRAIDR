# DexScreener Scan Report

Date: 2026-05-24

## Commands

Offline fixture scan:

```powershell
python -m cli.main scan --fixture
```

Read-only DexScreener scan:

```powershell
python -m cli.main scan --source dexscreener --pair-ref <chain>/<pairAddress>
```

Persist scan evidence and read it through radar:

```powershell
python -m cli.main scan --source dexscreener --pair-ref <chain>/<pairAddress> --database storage/duckdb/traidr_scan_test.duckdb
python -m cli.main radar --database storage/duckdb/traidr_scan_test.duckdb
```

## Behavior

- DexScreener scans use the public read-only endpoint `/latest/dex/pairs/{chainId}/{pairId}`.
- Responses are normalized into existing `NormalizedMarketSnapshot` and `MarketScanCandidate` models.
- Scan evidence is persisted to DuckDB only when `--database` is provided.
- Radar can display scan evidence from DuckDB, but it remains non-executable.
- All scan and radar outputs include `can_execute_trades: False` where relevant.

## Failure Policy

- Missing `--source` in non-fixture mode returns `INSUFFICIENT_DATA` with instructions.
- Network failures return `INSUFFICIENT_DATA`.
- HTTP errors return `INSUFFICIENT_DATA`.
- Missing price, liquidity, or volume fields return `INSUFFICIENT_DATA`.
- No scan result can execute trades, withdrawals, or wallet actions.

## Limitations

- Tests mock DexScreener responses and do not require internet.
- Live DexScreener availability depends on external network access and API uptime.
- TRAIDR does not rate-limit batches beyond one request per supplied pair reference in this phase.
