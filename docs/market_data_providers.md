# External Market Data Providers

TRAIDR uses one read-only provider boundary so public sources can be combined without allowing any provider to create an order or change paper state.

## Provider roles

| Provider | Data | Authentication | Role |
| --- | --- | --- | --- |
| Bitunix public REST/WebSocket | Candles, tickers, depth, trades, funding and market events | None for public data | Primary venue-specific futures feed |
| Bitunix private boundary | Future balance, positions, leverage and TP/SL visibility | Deferred; no client implemented | Disabled account-read boundary only |
| CoinGlass V4 | Funding, open interest, OI changes, liquidations and long/short ratios | API key required by current API | Cross-exchange derivatives context |
| CoinGecko | Current and historical market data and metadata; existing CoinGecko/DEX evidence covers liquidity where available | Keyless public API by default | Cross-market and identity-bound context |
| CoinMarketCap | Quotes, rankings, trends and content; technical indicators use TRAIDR deterministic features | Keyless routes where supported; full catalog requires API key | Market ranking and narrative context |

CoinMarketCap's current public API does not expose documented event-calendar or technical-indicator endpoints in the provider contract. TRAIDR returns CMC_EVENTS_API_UNAVAILABLE rather than scraping or fabricating token events.

## Code boundaries

- data_pipeline/provider_contracts.py defines the provider protocol, normalized observations, health, cache, timestamp normalization, source conflict records and deterministic merging.
- data_pipeline/market_data_providers.py implements the Bitunix facade, CoinGlass V4, CoinGecko keyless current/history, CoinMarketCap quotes/rankings/trending/content, and the disabled Bitunix private boundary.
- data_pipeline/provider_factory.py builds the read-only set without persisting credentials.
- scheduler/live_service.py enriches evidence with optional CoinGlass/CoinMarketCap context; keys are read from process environment only.
- storage/schema.py and storage/market_repository.py persist schema-v8 scanner breakdowns; dashboard/pages/live_scanner.py renders them read-only.
- scoring/live_scanner.py combines providers and returns a factor-by-factor research score.
- Existing data_pipeline/bitunix_websocket.py, data_pipeline/microstructure.py, data_pipeline/provider_runtime.py, and scheduler/live_service.py remain the source of truth for streaming trades, order-flow aggregation, throttling, circuits, ingestion gaps and DuckDB writes.

## Runtime behavior

Each provider has:

- UTC timestamp normalization and future-clock rejection.
- In-memory TTL caching.
- Token-bucket throttling.
- Retry-After-aware retry behavior.
- Circuit-breaker state.
- Latency, clock-skew, failure and rate-limit health.
- Explicit INSUFFICIENT_DATA results for missing keys, missing mappings, malformed responses, unavailable endpoints and transport failures.

The merger prefers venue-specific Bitunix fields, then CoinGlass, CoinGecko and CoinMarketCap. It retains every source observation and emits SOURCE_CONFLICT_WARNING; conflicts in critical fields such as price, funding or open interest become CRITICAL_SOURCE_CONFLICT and block scanner direction.

## Scanner factors

The scanner uses deterministic weights:

- price structure: 20%
- volume: 10%
- order-book imbalance: 10%
- recent trades: 10%
- funding: 10%
- open-interest change: 10%
- liquidation pressure: 10%
- BTC/ETH correlation: 5%
- news/catalyst: 5%
- risk/reward: 10%

Every factor includes its raw value, normalized value, long/short contribution, source, and explanation. If any required factor is absent, the scanner returns INSUFFICIENT_DATA and NO_TRADE. A complete but weak setup returns NO_TRADE; a source conflict returns DEGRADED and NO_TRADE.

The scanner output always contains can_execute_trades: false. It has no order, leverage, cancellation, reversal or withdrawal method.

## Optional key handling

Keys are passed to provider constructors only. They are not stored in DuckDB, scanner payloads, logs, prompts or dashboard output. Without a CoinGlass or full CoinMarketCap key, the relevant provider remains present but returns a truthful insufficient-data state.

The disabled Bitunix private boundary deliberately has no signing, authentication, order, leverage-change, cancellation or withdrawal implementation.
