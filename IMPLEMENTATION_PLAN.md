# TRAIDR Canonical Implementation Plan

Plan revision: 2026-08-04

Planning baseline reviewed: `7afa4fd` plus the current accuracy/intelligence workstream

Target release: `v0.2.0`

Required runtime: CPython `>=3.11,<3.12`

Operating posture: local-first, simulation-first, read-only market research

This is the single source of truth for implementation, verification, certification, and release work. It supersedes the older MVP phase plan and consolidates `docs/PRODUCTION_READINESS_STATUS.md`, `docs/PRODUCTION_RESEARCH_SERVICE.md`, `docs/PRODUCTION_CERTIFICATION.md`, `docs/SOL_VERIFICATION_HANDOFF.md`, `TEST_PLAN.md`, and `SAFETY_RULES.md`.

## 1. Target outcome

TRAIDR `v0.2.0` is complete only when it can continuously collect public crypto-market evidence, produce deterministic and explainable research decisions, simulate futures locally, reproduce historical results, and prove its safety and reliability through certification evidence.

The release is not a profitability claim and is not real-money trading software.

Definition of done:

1. Required evidence is fresh, correctly timestamped, conflict-checked, and traceable to its source.
2. Missing, stale, malformed, contradictory, or unsafe evidence returns `HOLD`, `NO_TRADE`, or `INSUFFICIENT_DATA`.
3. Backtests, paper accounting, persistence, recovery, and dashboard views are deterministic and auditable.
4. The complete verification and 72-hour certification gates pass on Python 3.11 and in GitHub Actions.
5. Live execution, private exchange actions, wallets, signing, transfers, withdrawals, and custody remain absent.

## 2. Non-negotiable safety contract

These requirements override feature requests, scores, models, agents, UI controls, and release pressure.

### 2.1 Required behavior

- Default to `HOLD` or `NO_TRADE`.
- Return `INSUFFICIENT_DATA` when required evidence is missing, stale, malformed, contradictory, unmapped, or uncertain.
- Apply anti-rug and deterministic risk vetoes after all model and signal calculations; vetoes are final.
- Keep paper simulation disabled by default and identify every simulated record explicitly.
- Keep credentials in operator-owned process memory only; never persist or expose them.

### 2.2 Prohibited capabilities

- No live order placement, cancellation, reversal, leverage change, or exchange-order routing.
- No wallet connection, private key, seed phrase, signing, bridging, transfer, withdrawal, or custody flow.
- No private exchange endpoint in the `v0.2.0` release.
- No raw LLM output connected to any broker, exchange, DEX router, wallet, or simulator mutation path.
- No secret-bearing value in prompts, TOON payloads, memory, logs, fixtures, reports, or DuckDB.

Any proposal that weakens this contract is rejected rather than hidden behind a feature flag.

## 3. Current implementation state

### 3.1 Completed and retained

| Capability | Implemented state | Release posture |
| --- | --- | --- |
| Bitunix public ingestion | REST and WebSocket candles, tickers, order book, trades, funding, reconnects, aggregation, gap detection, and recovery | Retain and regression-test |
| Asset identity | Reviewed exact mappings for BTCUSDT and HYPEUSDT; unmapped assets do not receive symbol-only cross-source joins | Retain fail-closed behavior |
| External research providers | Unified read-only contracts; CoinGlass core and expanded shadow metrics, CoinGecko, CoinMarketCap, CryptoPanic, caching, health, rate limiting, capability/cost/quota/licensing metadata, and conflict structures | Live keyed verification remains gated |
| Evidence and decisions | Multi-horizon features, order flow, funding, basis, liquidity, contradiction detection, deterministic decisions, and reason codes | Retain safety-veto precedence |
| Backtesting and calibration | Forward-only labeling, walk-forward tests, overlap exclusion, replay hashing, local artifacts, and calibration gates | External evidence gates remain open |
| Paper futures | Long/short positions, partial fills, fees, funding, slippage, stops, targets, liquidation, stress, recovery, and reconciliation | Simulation only; disabled by default |
| Persistence and dashboard | DuckDB schema v9, scanner and zero-weight shadow-evidence persistence, read-only cockpit, scanner, evidence, provider health, derivatives regime, news context, paper portfolio, and audit views | Add schema-v9 migration/restore/browser proof |
| Certification tooling | `certify shadow`, `certify status`, `certify report`, fault injection, backup and replay gates | 72-hour run still pending |

### 3.2 Verified blockers and open gaps

| Priority | Gap | Evidence | Required outcome |
| --- | --- | --- | --- |
| P0 | Optional CoinGlass, CoinMarketCap, and CryptoPanic authenticated paths lack controlled operator-key evidence | Keys are intentionally absent from fixtures and the current process | Run secret-safe live shadow verification |
| P1 | Schema-v9 migration/restore and browser behavior need release evidence | Focused persistence/API/frontend tests exist | Add migration fixture, restore proof, and browser screenshots |
| P1 | Shadow feature promotion evidence does not yet exist | All new features are fixed at zero scoring weight | Run ablation and leakage-safe walk-forward validation |
| P2 | BTC/ETH regime breadth and DeFiLlama unlock-risk expansion remain incomplete | Current cross-market checks are narrower than the target regime layer | Add deterministic adapters only after P0 stability |
| P2 | MCPs are not configured at user level | Repository boundary is research-only and injection tested | Operator configures CoinGecko/CMC/Dune; Nansen remains optional |
| P2 | Full-repository mypy retains older certification-module errors | Changed files pass strict mypy | Resolve or approve a documented debt boundary before release |
| External | GitHub Actions billing/account access, 72-hour shadow, backup restore, repeated replay, and calibration evidence remain open | Production certification documents | Complete before tagging `v0.2.0` |

## 4. Target architecture

```text
Public REST/WebSocket + optional read-only research APIs
                         |
                         v
        Unified provider contracts and health states
                         |
             freshness + identity + conflict gate
                         |
                         v
       deterministic ten-factor research scanner
                         |
             final safety/risk veto authority
                         |
            +------------+-------------+
            |                          |
            v                          v
     DuckDB audit state        paper-only simulator
            |
            v
     read-only dashboard
```

Architectural rules:

- Providers expose observations and health, never actions.
- The merge layer owns source precedence, freshness rejection, timestamp normalization, and conflict warnings.
- The scanner owns deterministic factor normalization and exact explanations, never data fabrication.
- The single-writer service owns DuckDB mutation; the dashboard opens read-only state.
- Paper simulation is a separate bounded consumer and cannot create live execution authority.

Detailed visual-platform workstream:

- `docs/VISUAL_PLATFORM_EXECUTION_PLAN.md` is the implementation-ready specification for the local SaaS-style browser application and evidence-grounded Ask TRAIDR chat.
- The visual workstream may start after Phase 1 passes, but it cannot bypass any verification, certification, or release gate in this plan.
- The existing Streamlit dashboard remains the verified fallback until the new application reaches tested feature parity.

## 5. Delivery roadmap

| Phase | Priority | Estimated effort | Depends on | Exit gate |
| --- | --- | ---: | --- | --- |
| 0. Restore reproducible environment | P0 | 30-90 minutes | Python 3.11 available | Fast verification commands execute |
| 1. Correct verified provider/scanner defects | P1 | 3-5 hours | Phase 0 | Focused and full tests pass |
| 2. Close persistence, migration, UI, and typing debt | P1 | 1-2 days | Phase 1 | Restore/browser/mypy decision recorded |
| 3. Complete independently verified scanner evidence | P2 | 2-4 days | Phase 2 | Ten factors can be complete without fabrication |
| 4. Controlled external-provider verification | P2 | 4-8 hours | Operator-owned keys and network access | Redacted provider evidence passes |
| 5. Run operational certification | Release gate | 72 real hours plus review | Phases 0-4 | Shadow report is `PASSED` |
| 6. Complete replay, restore, and calibration evidence | Release gate | 4-8 hours plus outcome collection | Stable shadow database | Replay/restore pass; calibration stays honest |
| 7. Release `v0.2.0` | Release gate | 1-2 hours | All preceding phases and CI | Signed-off tag and evidence manifest |

Effort estimates are engineering time, not elapsed certification or data-collection time.

### Accuracy and intelligence delivery status

| Work package | State | Acceptance evidence |
| --- | --- | --- |
| Secure provider metadata and key boundaries | Implemented | Keys remain process-only; health exposes non-secret capability, quota, cost, freshness, and licensing metadata |
| CoinGlass expanded derivatives collection | Implemented in shadow mode | 5m/15m/1h/4h OI change, weighted funding, liquidation acceleration, ratios, taker flow, and crowding normalize with zero weight |
| CryptoPanic catalyst context | Implemented in shadow mode | Duplicate headlines group; news cannot emit a directional factor |
| Four-layer derivatives classification | Implemented as descriptive shadow assessment | Explicit setup/regime/crowding/squeeze/catalyst/data-quality fields; decision remains `NO_TRADE` and probability `UNCALIBRATED` |
| MCP research safety boundary | Implemented | Citations and freshness required; prompt injection and action requests are quarantined; scoring weight is zero |
| React intelligence visibility | Implemented | Provider readiness, shadow regime, catalyst timeline, and score explanations distinguish observed versus derived evidence |
| Promotion to production scoring | Not authorized | Requires every gate in Section 8 and at least 500 independent out-of-sample outcomes |

Dependencies before promotion: operator-owned API keys, stable network access, synchronized outcome history, three or more walk-forward folds, deterministic replay evidence, and completed schema-v9 restore/browser certification.

## 6. Phase specifications

### Phase 0 - Restore reproducible Python 3.11 verification

Owner: operator for Python installation; developer for repository verification.

Work:

1. Provision CPython 3.11 without changing the project's version range.
2. Recreate `.venv` from `requirements.lock` and install the local package.
3. Record Python, pip, DuckDB, Streamlit, Playwright, Ruff, and mypy versions.
4. Run the fast verification sequence before changing runtime code.
5. Save results in the implementation report or release evidence.

Acceptance criteria:

- `python --version` reports 3.11.x inside `.venv`.
- Locked dependencies install without resolution drift.
- Pytest, focused mypy, imports, and Ruff execute successfully.
- No credential is required for the baseline suite.
- A clean checkout can reproduce the same setup commands.

Commands:

```powershell
uv venv .venv --python 3.11
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe --explicit-package-bases data_pipeline/market_data_providers.py data_pipeline/provider_factory.py scoring/live_scanner.py
.\.venv\Scripts\python.exe -c "import dashboard.app; import data_pipeline.market_data_providers; import scoring.live_scanner; print('imports ok')"
```

### Phase 1 - Fix verified provider and scanner defects

Dependencies: Phase 0.

Work package A - freshness:

- Define maximum observation ages by capability or field family.
- Filter stale observations before source selection.
- Return `INSUFFICIENT_DATA` when required evidence has no fresh source.
- Propagate age, threshold, provider, and reason code to storage and dashboard evidence.
- Add boundary tests for fresh, exactly-at-limit, stale, mixed-age, and future-skewed observations.

Work package B - rate limits:

- Normalize response-header keys once or use a case-insensitive accessor.
- Honor numeric and HTTP-date `Retry-After` values.
- Keep retry sleep bounded and circuit behavior deterministic under injected clocks/sleep.
- Preserve explicit `PROVIDER_RATE_LIMITED` health and reason codes.
- Add lowercase, uppercase, malformed, absent, and oversized-header tests.

Work package C - factor evidence:

- Pass available field values into unavailable-factor construction.
- Preserve raw value, source, and an explanation for evidence that was present.
- Keep normalized contribution, long contribution, and short contribution at zero when the scan is halted.
- Preserve `INSUFFICIENT_DATA` and `NO_TRADE` until every required factor is eligible.
- Test persisted and dashboard-loaded factor JSON, not only the in-memory object.

Acceptance criteria:

- A six-hour-old required observation cannot produce `HEALTHY`, `LONG`, or `SHORT`.
- Provider-specific rate-limit timing is honored without unbounded sleeping.
- Incomplete scans show truthful available raw evidence and zero contribution.
- Every changed behavior has a focused regression test.
- Full tests, Ruff, focused mypy, imports, compilation, and the safety scan pass.

### Phase 2 - Persistence, migration, dashboard, and typing proof

Dependencies: Phase 1 green.

Work:

1. Test additive migration from the previous schema to schema v8 with `market_scanner_scores` retained after repeated initialization.
2. Test backup and restore of scanner rows, factor JSON, conflicts, reason codes, timestamps, and `can_execute_trades = FALSE`.
3. Add browser coverage for empty, complete, insufficient, degraded, stale, and conflicting Live Scanner states.
4. Test dashboard read-only behavior and prove no scanner control can mutate exchange or portfolio state.
5. Triage the 87 older mypy errors into fix-now versus documented legacy debt; do not weaken checks globally.

Acceptance criteria:

- Migration and restore preserve all scanner evidence exactly.
- Browser tests show the correct state and exact factor details for every safety state.
- Dashboard tests detect accidental execution controls or writable exchange actions.
- New and modified provider/scanner/service/storage/dashboard files pass strict mypy.
- Any deferred typing debt has named files, owner, rationale, and a post-release milestone.

### Phase 3 - Complete independently verified scanner evidence

Dependencies: Phases 1-2; canonical BTC and ETH identities; sufficient synchronized history.

BTC/ETH correlation adapter:

- Compute correlation from synchronized, closed candles using documented return intervals and lookback.
- Reject insufficient overlap, stale anchors, gaps, mixed intervals, and identity mismatches.
- Persist lookback, sample count, interval, source timestamps, value, and reason codes.
- Prevent BTC/ETH self-correlation from being presented as independent confirmation.

Directional catalyst adapter:

- Use allowlisted read-only news/event sources with publication timestamps and canonical identity mapping.
- Separate relevance, direction, reliability, novelty, and age decay.
- Deduplicate repeated headlines and reject undated, unmapped, stale, or contradictory claims.
- Keep neutral or uncertain evidence neutral; never infer a bullish catalyst from missing data.

Acceptance criteria:

- Both factors are deterministic from stored input evidence.
- Every value contains source, observed time, calculation/version metadata, and explanation.
- Missing or contradictory inputs keep the scanner at `INSUFFICIENT_DATA` or `NO_TRADE`.
- Historical tests prove no future news or candle enters a score.
- Complete ten-factor scores remain research-only with `can_execute_trades = false`.

### Phase 4 - Controlled provider verification

Dependencies: operator-owned CoinGlass/CoinMarketCap keys, approved network window, Phase 1 rate-limit fix.

Work:

1. Inject keys through the local process environment only; never place them in commands, files, logs, prompts, reports, fixtures, or DuckDB.
2. Verify CoinGlass funding, OI, OI change, liquidation, and long/short parsing against documented responses.
3. Verify CoinMarketCap supported rankings, quotes, trends, and content routes; unsupported endpoints remain explicit unavailable states.
4. Exercise health, timeout, authentication failure, rate limit, cache, stale timestamp, and source-conflict behavior.
5. Produce a redacted verification report containing endpoint class, status, latency, timestamps, and reason codes only.

Acceptance criteria:

- Secret scans find no key material before or after the run.
- Every provider remains read-only and reports `can_execute_trades = false`.
- Authentication failure and rate limiting fail closed without retry storms.
- Provider timestamps remain within configured skew/freshness bounds.
- MCP bridges, if later added, implement the same provider contract and cannot expose action tools.

### Phase 5 - 72-hour collection-only shadow certification

Dependencies: Phases 0-4 green, stable local disk, backup destination, public Bitunix availability.

Work:

1. Start `certify shadow`, then run the single-writer service continuously for 72 real hours.
2. Keep automatic paper simulation disabled for the entire window.
3. Monitor heartbeats, coverage, age, reconnects, sequence gaps, circuits, conflicts, backups, disk, and service exits.
4. Preserve structured logs, backup evidence, certification state, and exact release commit.
5. Restart the gate if continuity or integrity requirements are violated; never edit elapsed time.

Acceptance criteria:

- Certification reports `PASSED`, not merely `RUNNING` or `INCOMPLETE`.
- Top-50 core coverage is at least 95%.
- Ticker p95 age is below 15 seconds and one-minute candle age is below 120 seconds.
- Every gap is `RESOLVED` or visibly `UNRESOLVED`; no stale heartbeat appears healthy.
- No paper order event occurs during collection-only certification.

### Phase 6 - Restore, replay, accounting, and calibration evidence

Dependencies: stable shadow database and at least one daily backup.

Work:

1. Restore a backup into a separate path and verify schema, safety flags, evidence, scanner scores, decisions, audit state, and read-only dashboard access.
2. Run the same multi-day replay twice from equivalent state and compare hashes, outcomes, fills, fees, funding, drawdown, and reconciliation.
3. Confirm stop-first same-candle ordering, overlap exclusion, idempotency, and no-lookahead behavior.
4. Continue collecting independent out-of-sample outcomes without relaxing the probability gate.
5. Preserve machine-readable restore, replay, reconciliation, and calibration reports.

Acceptance criteria:

- Restore succeeds without mutating the source database or losing safety metadata.
- Replay hashes and accounting outputs match exactly within the one-micro-dollar policy.
- No future candle, outcome, or news item influences an earlier decision.
- At least 500 independent outcomes and expected calibration error at most 5% are required per eligible bucket.
- Until calibration passes, the dashboard displays `uncalibrated` and no fabricated probability.

### Phase 7 - Release `v0.2.0`

Dependencies: every prior phase passed; GitHub account and Actions operational; maintainer approval.

Work:

1. Freeze the candidate commit and confirm a clean working tree.
2. Run the complete local release matrix and push the exact candidate.
3. Require green GitHub Actions on that exact SHA.
4. Assemble the certification, backup/restore, replay, reconciliation, dependency, and safety evidence manifest.
5. Create `v0.2.0` only after maintainer sign-off; do not retag a different commit.

Acceptance criteria:

- Local and CI verification are green on Python 3.11.
- Certification state is `PASSED` and evidence identifies the release SHA.
- Backup restore and repeated replay evidence pass.
- Automatic paper simulation remains disabled by default.
- Forbidden-capability and secret scans pass on the release artifact.

## 7. Required test matrix

### Fast change gate

Run after each focused implementation change:

```powershell
.\.venv\Scripts\python.exe -m pytest -q <focused-test-files>
.\.venv\Scripts\ruff.exe check <changed-files>
.\.venv\Scripts\mypy.exe --explicit-package-bases <changed-production-files>
```

### Full local gate

Run before a phase is marked complete:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe --explicit-package-bases intelligence data_pipeline execution risk scoring storage config
.\.venv\Scripts\python.exe -m compileall -q agents alerts ask cli config dashboard data_pipeline execution intelligence lifecycle memory notifications onchain operator portfolio radar reports risk scheduler scoring sentiment storage technicals thesis token_detail utils watchlist
node --check dashboard/components/chart_engine.js
.\.venv\Scripts\python.exe scripts/forbidden_capability_scan.py
.\.venv\Scripts\python.exe scripts/certification_smoke.py
```

### Behavior coverage required for every relevant change

| Area | Minimum proof |
| --- | --- |
| Provider | Parsing, timestamp/skew, stale data, timeout, rate limit, cache, conflict, malformed response, missing key, and read-only authority |
| Scanner | Every factor, threshold boundaries, missing/available evidence, conflicts, stale input, weak evidence, deterministic ordering, and exact explanation |
| Persistence | Additive migration, idempotency, duplicate write, restart, backup, restore, JSON round-trip, and `can_execute_trades = false` |
| Dashboard | Empty/healthy/degraded/insufficient states, factor rendering, read-only access, offline behavior, and no execution controls |
| Backtest/paper | No-lookahead, stop-first collision, overlap exclusion, fees, funding, slippage, liquidation, stress, restart, and reconciliation |
| Safety | Forbidden capability search, secret boundary, deterministic veto precedence, and non-actionable LLM output |

No paid API or real secret is required by automated tests. Controlled credential checks are separate operator-run evidence.

## 8. Release and certification gates

A gate is binary. An incomplete gate blocks the release.

| Gate | Pass evidence | Failure behavior |
| --- | --- | --- |
| Runtime | Reproducible Python 3.11 locked environment | Stop verification |
| Correctness | Full tests, strict changed-file typing, compilation, deterministic replay | Block phase/release |
| Safety | Forbidden-capability and secret scans; fail-closed tests | Reject change |
| Data quality | Freshness, identity, coverage, gap, conflict, and health thresholds pass | Return insufficient/no-trade |
| Recovery | Separate-path backup restore and idempotent migration pass | Certification incomplete |
| Operations | 72 continuous hours and certification `PASSED` | Do not tag |
| Calibration | 500 independent outcomes and ECE <= 5% per bucket | Keep `uncalibrated` |
| CI | Green GitHub Actions on exact release SHA | Do not tag |
| Approval | Maintainer reviews evidence manifest and release diff | Keep production-candidate status |

## 9. Responsibility split

### Developer/Codex work

- Implement Phases 1-3 with focused tests and smallest safe patches.
- Build migration, restore, browser, typing, and safety proof.
- Prepare deterministic operator commands and redacted report templates.
- Keep documentation, schema version notes, and the knowledge graph current.
- Commit and push only verified, scoped changes with a clean diff.

### Operator/user work

- Install or authorize Python 3.11 and preserve the local machine during environment setup.
- Own provider keys and enter them only into the approved local process environment.
- Keep the machine, public network connection, disk, and service running for the 72-hour gate.
- Resolve GitHub billing/account access so Actions can run.
- Review certification evidence and approve the release tag.

## 10. Deferred and prohibited work

Not part of `v0.2.0`:

- Bitunix private account visibility, even if nominally read-only.
- Additional instruments without reviewed canonical identity mappings.
- Probability display for buckets that have not passed calibration.
- Automatic paper simulation during shadow certification.
- Scraped or fabricated CoinMarketCap events/technical indicators.

Permanently prohibited under this product boundary:

- Real-money or testnet order execution.
- Exchange order placement, cancellation, reversal, or leverage mutation.
- Wallets, signing, private keys, seed phrases, custody, transfers, and withdrawals.
- Autonomous processes with financial execution authority.
- Profit guarantees or daily-profit targets as acceptance criteria.

## 11. Change protocol

For every implementation task:

1. Name the active phase, exact acceptance criterion, and files in scope.
2. Add a failing focused test that demonstrates the missing behavior.
3. Implement the smallest safe patch and preserve explicit reason codes.
4. Run focused checks, then the full local gate; do not push failures.
5. Update this plan only when scope, evidence, dependencies, or gate status changes.

## 12. Immediate execution sequence

Do these next, in order:

1. Restore `.venv` on Python 3.11 and rerun the fast verification sequence.
2. Implement the stale-observation veto with boundary tests.
3. Fix case-insensitive `Retry-After` handling and truthful unavailable-factor evidence.
4. Run the full verification matrix and record the new exact baseline.
5. Add scanner migration/restore and Live Scanner browser coverage.

Do not begin provider-key validation or the 72-hour shadow window until these five steps pass.
