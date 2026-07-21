# Production Readiness Status

Date: 2026-07-21

TRAIDR `0.2.0` is implemented as a local-first public-market research and paper-futures production candidate.
It is not real-money trading software and does not guarantee profitability. Release tagging remains blocked until
the time-based shadow certificate passes.

## Completed Implementation

- CPython 3.11.15 local environment, a 73-package lock file, Ruff, strict production-module mypy, and Windows/Ubuntu CI.
- Current Bitunix REST/WebSocket contracts, exact endpoint failures, schema fingerprints, freshness, reconnects,
  one-minute streaming, deterministic 5m/15m/1h/4h/1d aggregation, bounded bootstrap, gap detection, and REST recovery.
- Reviewed canonical identities and exact source bindings for BTCUSDT and HYPEUSDT. Unmapped instruments remain
  Bitunix-only; symbol-only cross-source joins are forbidden.
- Keyless CoinGecko spot/metadata, contract-address-only DEX boundaries, allowlisted RSS context, and read-only
  Solana mint/freeze/supply/holder evidence. Missing mappings stay missing.
- Versioned evidence bundles covering technicals, order flow, funding/basis, cross-market disagreement, news context,
  and on-chain safety. Verified honeypot, inaccessible liquidity, unsafe control, freeze/sell restriction, or
  contradictory identity evidence hard-vetoes a setup.
- Forward-only continuous outcomes with conservative same-candle stop-first ordering and overlapping-sample exclusion.
- Persisted chronological walk-forward backtests, deterministic replay hashes, side/horizon champion-challenger
  training, local SHA-256 artifact manifests, rollback pointers, and strict probability display gates.
- Paper futures with long/short positions, partial depth fills, latency/slippage, idempotent scheduled funding,
  trailing/expiry/target/gap/liquidation handling, correlation and simultaneous-loss stress, restart recovery, and
  one-micro-dollar accounting reconciliation.
- Read-only cockpit panels for evidence, feature contradictions, order book/flow, funding/basis, news, on-chain,
  calibration, model artifacts, paper margin/stress/funding/drawdown, gaps, provider circuits, and decision changes.
- Python Playwright browser coverage for preview watermark, timeframe changes, local chart rendering, pan/zoom,
  offline health warnings, and allowlisted System Health controls; Streamlit AppTest remains the fast smoke layer.
- `traidr certify shadow`, `traidr certify status`, and `traidr certify report`, with deterministic fault injection,
  coverage/freshness/integrity/backup/replay gates, and truthful `RUNNING`, `INCOMPLETE`, `FAILED`, or `PASSED` states.

## Verification Completed

- 282 tests pass on CPython 3.11.15, including browser E2E.
- Ruff passes.
- Strict mypy passes across 70 production source files; named legacy normalizers retain scoped practical overrides.
- Python compilation, local chart JavaScript syntax, forbidden-capability scan, and migration/backup-restore smoke pass.
- A fresh live-public run completed against Bitunix and the exact-bound CoinGecko cross-check, persisted validated
  records, reported healthy REST analysis, and retained `can_execute_trades: false`.
- The static safety suite confirms live orders, private endpoints, credentials, wallets, signing, custody, transfers,
  and withdrawals remain absent.

## Honest External Gates Still Open

1. Run `traidr certify shadow` with the service continuously for 72 real hours. Elapsed time is never fabricated.
2. During that run, maintain at least 95% top-50 Bitunix coverage, ticker p95 age below 15 seconds, and one-minute
   candle availability within two intervals; every gap must be recovered or visibly `UNRESOLVED`.
3. Produce and restore a daily service backup during the shadow window.
4. Run the same multi-day paper replay at least twice and obtain identical hashes with exact reconciliation.
5. Accumulate at least 500 independent out-of-sample outcomes in an applicable side/horizon bucket before displaying
   a percentage. Until then the UI correctly displays `uncalibrated`.
6. Create tag `v0.2.0` only after the shadow report state is `PASSED` and the pushed GitHub Actions run is green.

Automatic paper simulation remains disabled throughout shadow certification. The rollout order is collection-only,
observe-and-recommend, manual paper approval, explicit deterministic auto-paper, and finally probability display for
eligible buckets only.
