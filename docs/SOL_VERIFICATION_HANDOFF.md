# TRAIDR Verification Handoff

Use this document as the short context packet for an external verification model.

## Mission

Verify TRAIDR as a local-first, simulation-first crypto market-research and paper-futures system. Analyze correctness, safety, reproducibility, and release readiness. Do not add live trading capability.

## Current checkout

- Repository: `leonartist7/TRAIDR`
- Branch: `codex/unified-market-providers-scanner`
- Latest commit: `d80832d`
- Required runtime: Python 3.11 (`>=3.11,<3.12`)
- Local environment: `.venv`
- Known result: `294 passed`
- Ruff: passed
- Focused mypy for the new provider/scanner modules: passed
- Full-repository mypy: 87 pre-existing errors in older modules
- Graphify update: currently blocked by a local graphify package/skill version mismatch

## Product safety boundary

TRAIDR must remain:

- Public-data and local-first by default.
- Paper/simulation only.
- Read-only with respect to exchanges.
- Fail-closed: use `HOLD`, `NO_TRADE`, or `INSUFFICIENT_DATA` when evidence is missing, stale, malformed, contradictory, or unsafe.
- Explicitly free of live orders, cancellations, reversals, leverage changes, withdrawals, transfers, custody, wallet signing, private keys, seed phrases, and private exchange endpoints.

Never expose credentials or secret-bearing environment variables to prompts, logs, fixtures, TOON payloads, memory, or DuckDB.

## Already implemented

Inspect these files first instead of scanning the whole repository:

| Area | Files |
|---|---|
| Unified providers | `data_pipeline/provider_contracts.py`, `data_pipeline/market_data_providers.py`, `data_pipeline/provider_factory.py` |
| Bitunix public feed | `data_pipeline/bitunix_futures_adapter.py`, `data_pipeline/bitunix_websocket.py`, `data_pipeline/microstructure.py` |
| External context | `data_pipeline/coingecko_adapter.py`, `data_pipeline/market_data_providers.py`, `intelligence/rss_adapter.py` |
| Scanner | `scoring/live_scanner.py` |
| Service integration | `scheduler/live_service.py` |
| Persistence | `storage/schema.py`, `storage/market_repository.py`, `dashboard/queries.py` |
| Dashboard | `dashboard/app.py`, `dashboard/pages/live_scanner.py` |
| Plan and boundaries | `IMPLEMENTATION_PLAN.md`, `docs/market_data_providers.md`, `SAFETY_RULES.md` |
| Focused tests | `tests/test_market_provider_scanner.py` |

Implemented provider capabilities include Bitunix public REST/WebSocket, CoinGlass derivatives context, CoinGecko current/history/metadata, CoinMarketCap quotes/rankings/trending/content boundaries, health checks, caching, rate limits, retries, timestamp normalization, source conflicts, and a ten-factor explainable scanner.

Bitunix private account visibility is represented only by a disabled boundary. It must stay disabled.

## Fast verification sequence

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe --explicit-package-bases data_pipeline/market_data_providers.py data_pipeline/provider_factory.py scoring/live_scanner.py
.\.venv\Scripts\python.exe -c "import dashboard.app; import data_pipeline.market_data_providers; import scoring.live_scanner; print('imports ok')"
```

The full mypy command is useful for baseline tracking but currently reports older repository errors. Do not attribute those errors to the provider phase unless the file is listed in the new-provider section above.

## Verification order

1. Confirm tests and focused static checks.
2. Review provider parsing, timestamp freshness, retry/rate-limit behavior, caching, and conflict precedence.
3. Review scanner fail-closed behavior and factor explanations.
4. Review schema-v8 scanner persistence and read-only dashboard rendering.
5. Run a safety search for order, leverage, cancellation, withdrawal, transfer, wallet, signing, and private-key capabilities.
6. Report release blockers before proposing code changes.

## Remaining work

Priority order:

1. Decide whether to fix the 87 older full-mypy errors now or track them separately.
2. Add migration/restore tests for the scanner table and browser coverage for the Live Scanner tab.
3. Add independently verified BTC/ETH correlation and directional news-catalyst adapters. Until then, complete scanner scores must remain unavailable.
4. Run controlled provider-key tests using operator-owned secrets; never commit or log the keys.
5. Complete 72-hour shadow certification, backup restore, replay verification, CI recovery, and the `v0.2.0` release gate.

## Rules for the verifier

- Do not rewrite architecture without evidence.
- Do not “fix” safety behavior by making the scanner more permissive.
- Do not fabricate provider data, calibration, correlation, news direction, or probabilities.
- Prefer a focused test and the smallest safe patch.
- If changing code, run focused tests, then the full test suite.
- Do not commit or push unless the requested change is verified and scoped.

## Required report format

Return:

1. `PASS`, `FAIL`, or `BLOCKED`.
2. Top three findings, ordered by severity.
3. Exact file and line for each finding.
4. Reproduction command and observed result.
5. Smallest safe fix, if one is required.
6. Tests run and tests not run.
7. Explicit confirmation that no execution or custody capability was introduced.

Start with the fast verification sequence. Do not read the entire repository unless a targeted check identifies a dependency that requires it.
