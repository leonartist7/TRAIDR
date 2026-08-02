# TRAIDR Current Implementation Plan

Status: current consolidated plan for baseline `edcf908`
Target release: `v0.2.0`
Runtime: CPython 3.11
Operating posture: local-first, simulation-first, public-data research only

This document supersedes the older MVP-only phase plan. It is the canonical implementation and release plan for the production-candidate architecture described in `docs/PRODUCTION_READINESS_STATUS.md`, `docs/PRODUCTION_RESEARCH_SERVICE.md`, `docs/architecture.md`, and `SAFETY_RULES.md`.

## 1. Non-negotiable safety contract

These constraints apply to every phase, test, fixture, dashboard control, adapter, and future change:

- No live order execution, authenticated exchange endpoints, private exchange data, wallet access, signing, transfers, withdrawals, custody, or private keys.
- Public adapters are read-only. The dashboard is read-only against DuckDB.
- The single-writer service is the only production writer.
- Paper futures are research accounting only and start disabled.
- Deterministic risk code is final authority over signals, models, agents, and UI controls.
- Missing, stale, malformed, contradictory, or unsafe evidence yields `HOLD`, `NO_TRADE`, or `INSUFFICIENT_DATA`.
- Probabilities remain `uncalibrated` until the independent-outcome and calibration gates pass.
- Any change that weakens these rules is a safety regression and must be rejected.

## 2. Repository reality at baseline

The following work is implemented and should be treated as completed unless a regression is found.

| Area | Current implementation | Status |
| --- | --- | --- |
| Runtime and packaging | Python 3.11 target, locked dependencies, CLI entry point, Windows/Ubuntu CI | Complete |
| Public ingestion | Bitunix REST/WebSocket contracts, strict endpoint handling, reconnects, bounded bootstrap, one-minute streaming, 5m/15m/1h/4h/1d aggregation, gap detection and REST recovery | Complete |
| Identity and cross-checks | Canonical BTCUSDT and HYPEUSDT bindings; CoinGecko spot/metadata checks; contract-address-only DEX boundary; allowlisted RSS context; read-only Solana safety evidence | Complete |
| Evidence quality | Freshness, schema, provenance, identity, sequence, coverage, contradiction, provider-circuit and ingestion-gap states | Complete |
| Research features | Multi-horizon technical features, order flow, funding, basis, liquidity, news, on-chain safety, evidence bundles and reason codes | Complete |
| Decisions | Deterministic explainable `LONG`, `SHORT`, `NO_TRADE` scoring with safety vetoes and nullable calibration output | Complete |
| Risk controls | Deterministic paper-risk gate, freshness/depth/mark-index checks, portfolio limits, drawdown halts, liquidation and stress controls | Complete |
| Backtesting | Forward-only outcomes, conservative same-candle stop-first ordering, overlap exclusion, chronological walk-forward backtests, replay hashes and no-lookahead checks | Complete |
| Model artifacts | Local SHA-256 manifests, side/horizon artifacts, champion/challenger metadata and rollback pointers | Complete |
| Paper futures | Long/short positions, partial depth fills, fees, latency/slippage, funding idempotency, trailing/expiry/target/gap/liquidation handling, restart recovery and reconciliation | Complete |
| Storage and service | Additive DuckDB schema, single-writer research service, durable heartbeats, health records, backups and structured local logs | Complete |
| Dashboard | Read-only Streamlit command center, native chart cockpit, overlays, evidence, health, paper portfolio, audit, calibration and model panels | Complete |
| Certification tooling | `certify shadow`, `certify status`, `certify report`; deterministic fault injection and truthful certification states | Complete |
| Verification assets | Unit/integration/safety tests, browser tests, Ruff, mypy, compilation, JavaScript syntax, forbidden-capability scan and migration/restore smoke | Complete by repository report; rerun locally before release |

The root `IMPLEMENTATION_PLAN.md` was previously an MVP bootstrap plan. Its old phases are historical context only; this document is the current source of truth.

## 3. Remaining work

### Phase A — Restore reproducible verification

Dependencies:

- A local checkout at the intended commit.
- CPython 3.11 and the locked dependency set.
- No exchange credentials or secrets.

Work:

1. Recreate the clean baseline environment.
2. Run the complete local verification matrix.
3. Record the actual test count and tool versions in the release evidence.
4. Resolve any drift between the repository report and reproducible local results.

Acceptance criteria:

- Python version is 3.11.
- Full test suite passes with no safety-test exclusions.
- Ruff, strict production mypy, compilation, JavaScript syntax, forbidden-capability scan, and migration/restore smoke pass.
- The browser suite and Streamlit smoke checks pass where their runtimes are installed.
- No secret, wallet, signing, private-endpoint, live-order, transfer, withdrawal, or custody capability appears in the scan.

Required checks:

```text
python -m pytest
python -m ruff check .
python -m mypy intelligence data_pipeline execution risk scoring storage config
python -m compileall -q agents alerts ask cli config dashboard data_pipeline execution intelligence lifecycle memory notifications onchain operator portfolio radar reports risk scheduler scoring sentiment storage technicals thesis token_detail utils watchlist
node --check dashboard/components/chart_engine.js
python scripts/forbidden_capability_scan.py
python scripts/certification_smoke.py
```

### Phase B — Complete the 72-hour collection-only shadow gate

Dependencies:

- Phase A passing.
- A continuously running local service.
- Public Bitunix availability.
- Stable local disk and backup destination.

Work:

1. Start `traidr certify shadow`.
2. Run the service in collection-only mode for at least 72 real hours.
3. Monitor System Health for feed lag, stale channels, reconnects, gaps, provider circuits, coverage and heartbeats.
4. Do not enable automatic paper simulation during this gate.
5. Preserve the generated report and service logs as release evidence.

Acceptance criteria:

- The certification state is truthful: `RUNNING`, `INCOMPLETE`, `FAILED`, or `PASSED`.
- At least 72 real hours have elapsed; elapsed time is never simulated.
- Top-50 Bitunix coverage is at least 95%.
- Ticker p95 age is below 15 seconds.
- One-minute candle availability is within two intervals.
- Every ingestion gap is recovered or visibly marked `UNRESOLVED`.
- No stale service heartbeat is silently treated as healthy.
- Paper simulation remains disabled throughout the collection-only gate.

### Phase C — Verify backup and restore

Dependencies:

- Phase B service run.
- A valid local backup produced during the shadow window.
- A separate restore destination.

Work:

1. Produce or retain a daily checkpoint backup.
2. Restore it into a separate DuckDB path.
3. Verify schema, heartbeats, health, evidence, decisions, paper state and audit records.
4. Confirm the original database remains unchanged.

Acceptance criteria:

- Restore completes without data loss or unsafe migration.
- Restored records retain safety flags and `can_execute_trades: false`.
- Backup/restore smoke passes on the supported runtime.
- The restored database can be opened read-only by the dashboard.
- A failed restore produces an explicit failure rather than a partial success claim.

### Phase D — Repeat deterministic replay and accounting verification

Dependencies:

- Persisted signals and forward outcome data.
- A stable database snapshot.
- Phase A verification.

Work:

1. Run the same multi-day replay twice from equivalent input state.
2. Compare replay hashes, labeled outcomes, fills, funding, fees, drawdown and reconciliation.
3. Confirm no future candle or outcome leaks into signal generation.
4. Preserve both run reports.

Acceptance criteria:

- Both replay hashes are identical.
- No-lookahead checks pass.
- Overlapping outcomes are excluded as designed.
- Same-candle stop/target collisions use conservative stop-first ordering.
- Paper accounting reconciles within the configured one-micro-dollar tolerance.
- Any mismatch blocks release and is reported with reason codes.

### Phase E — Accumulate and validate out-of-sample calibration evidence

Dependencies:

- Forward-only outcome labeling.
- Sufficient independent outcomes in an applicable side/horizon bucket.
- Walk-forward backtest and artifact persistence.

Work:

1. Continue collecting independent outcomes.
2. Recompute calibration reports chronologically.
3. Keep probabilities hidden while any gate is unmet.
4. Promote a model only through the existing champion/challenger and rollback path.

Acceptance criteria:

- At least 500 independent out-of-sample outcomes exist for the applicable bucket.
- Expected calibration error is at most 5%.
- Coverage and data-quality gates pass.
- No active quality veto, unresolved gap, identity contradiction or safety veto affects the displayed bucket.
- Otherwise the UI continues to display `uncalibrated`, never a fabricated percentage.

### Phase F — Release and controlled rollout

Dependencies:

- Phases A–E complete.
- GitHub Actions available and green.
- Maintainer review of certification artifacts.

Rollout order:

1. Collection-only shadow.
2. Observe-and-recommend.
3. Manual paper approval.
4. Explicit deterministic auto-paper, only if separately approved.
5. Probability display only for eligible calibrated buckets.

Acceptance criteria:

- Certification report state is `PASSED`.
- Backup/restore evidence is attached.
- Repeated replay hashes match.
- The full verification matrix is green.
- GitHub Actions has completed successfully after the billing/account blocker is resolved.
- Tag `v0.2.0` is created only after all preceding gates pass.
- Automatic paper simulation is still disabled by default.
- No release artifact contains credentials, private endpoints, wallet/signing code, withdrawal/transfer paths, or live execution.

## 4. Dependencies and ownership

| Dependency | Needed for | Failure behavior |
| --- | --- | --- |
| CPython 3.11 | Runtime and release verification | Fail the release gate |
| Locked Python dependencies | Reproducible tests and service | Stop and report installation drift |
| Public Bitunix availability | Shadow collection and live-public health checks | Record degraded/insufficient data; never infer a signal |
| Local DuckDB and disk | Durable service, paper state and audit history | Stop writes safely; surface the error |
| Backup destination | Shadow certification and recovery evidence | Certification remains incomplete |
| Historical forward outcomes | Backtest and calibration | Keep probabilities uncalibrated |
| GitHub Actions availability | Release CI gate | Do not tag until the billing/account blocker is resolved |
| Maintainer review | Release approval | Keep release candidate status |

## 5. Test requirements for future changes

Every runtime behavior change must include focused tests for:

- Missing, stale, malformed and contradictory evidence.
- Default `HOLD`, `NO_TRADE` or `INSUFFICIENT_DATA` behavior.
- Safety veto precedence over bullish technical or model output.
- Idempotency and restart recovery where state is persisted.
- No-lookahead, replay determinism and accounting reconciliation where backtest/paper logic changes.
- Read-only dashboard behavior and explicit `can_execute_trades: false` markers where UI changes.
- Forbidden-capability regressions whenever boundaries, adapters, controls or dependencies change.

Dashboard changes additionally require the relevant Streamlit smoke and Playwright/browser checks. Documentation-only changes do not require new behavior tests, but the existing verification suite must remain green before release.

## 6. Release evidence checklist

Before tagging:

- [ ] Clean working tree at the reviewed release commit.
- [ ] Local Python 3.11 environment reproduced.
- [ ] Full tests pass; no tests skipped for convenience.
- [ ] Ruff, mypy, compilation and JavaScript checks pass.
- [ ] Forbidden-capability scan passes.
- [ ] Migration/backup-restore smoke passes.
- [ ] 72-hour shadow report is `PASSED`.
- [ ] Coverage, freshness and gap thresholds are met.
- [ ] Backup was restored successfully during the shadow window.
- [ ] Repeated replay hashes match with exact reconciliation.
- [ ] Calibration gate is satisfied before any probability is displayed.
- [ ] GitHub Actions is green after the billing/account blocker is resolved.
- [ ] `v0.2.0` tag is created only after all gates above pass.

## 7. Explicitly deferred or permanently prohibited

Permanently prohibited:

- Live trading and exchange order routing.
- Private exchange endpoints or credentials.
- Wallets, private keys, seed phrases, signing, custody, transfers and withdrawals.
- Autonomous real-money processes.
- Direct LLM access to broker, exchange, DEX, wallet or signing APIs.

Deferred until separately justified and still safety-gated:

- Additional independently verified public cross-check providers.
- Larger out-of-sample datasets and champion/challenger research.
- Broader instrument coverage where canonical identity and evidence contracts exist.
- Operational observability improvements that do not create execution authority.

No feature should be added merely to increase trade frequency or target a daily profit amount. The platform’s objective is reproducible, explainable, fail-closed research.
