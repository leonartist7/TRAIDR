"""Always-on local research service for public data, signals, and health."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from config.runtime_settings import ResearchSettings, load_research_settings
from data_pipeline.asset_identity import AssetIdentityRegistry
from data_pipeline.bitunix_futures_adapter import BitunixFuturesAdapter
from data_pipeline.bitunix_models import (
    BitunixCandle,
    BitunixDepthSnapshot,
    BitunixFundingRate,
    BitunixTicker,
    BitunixTradingPair,
)
from data_pipeline.bitunix_websocket import BitunixPublicStream
from data_pipeline.candle_pipeline import OneMinuteCandlePipeline, aggregate_candles, expected_one_minute_range
from data_pipeline.microstructure import MicrostructureAccumulator
from data_pipeline.provider_runtime import ProviderCircuitBreaker, TokenBucket
from data_pipeline.coingecko_adapter import CoinGeckoAdapter, default_coingecko_transport
from data_pipeline.market_data_providers import CoinGlassProvider, CoinMarketCapProvider
from execution.paper_futures import PaperFuturesSimulator
from execution.portfolio_stress import assess_portfolio_stress
from intelligence.evidence_engine import (
    ALLOWLISTED_RSS_FEEDS,
    build_evidence_bundle,
    map_news_evidence,
)
from intelligence.rss_adapter import RSSNewsAdapter, default_rss_transport
from intelligence.production_models import (
    DataHealth,
    DataMode,
    FeatureSnapshot,
    IngestionGap,
    IngestionGapStatus,
    MarketChannel,
    MarketEvent,
)
from risk.production_gate import assess_paper_signal
from scoring.signal_engine import score_directional_setup
from scoring.live_scanner import ScannerInput, ScannerScore, score_scanner_input
from scoring.model_lifecycle import train_eligible_buckets
from scoring.outcome_labeler import label_expired_signals
from scheduler.control_api import LocalControlServer
from storage.duckdb_store import DuckDBStore
from storage.market_repository import MarketRepository
from storage.schema import initialize_schema
from technicals.multi_horizon import build_multi_horizon_features
from utils.structured_logging import configure_service_logger


class LiveResearchService:
    """One writer, public inputs only, and no route to any exchange action."""

    def __init__(
        self,
        settings: ResearchSettings | None = None,
        *,
        adapter: BitunixFuturesAdapter | None = None,
        database_path: str | Path | None = None,
    ) -> None:
        self.settings = settings or load_research_settings("live_public")
        if self.settings.profile.data_mode is not DataMode.LIVE_PUBLIC:
            raise ValueError("always-on network service requires live_public profile")
        self.adapter = adapter or BitunixFuturesAdapter()
        self.database_path = Path(database_path) if database_path else self.settings.service.resolved_database_path()
        self.started_at = datetime.now(tz=UTC)
        self.stop_event = asyncio.Event()
        self.active_symbols: tuple[str, ...] = self.settings.service.watchlist
        self._analysis_cursor = 0
        self._stream: BitunixPublicStream | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._control_queue: asyncio.Queue[tuple[str, str, dict[str, Any]]] = asyncio.Queue()
        self.paper_simulation_enabled = self.settings.service.paper_simulation_enabled
        self.paper_simulator = PaperFuturesSimulator()
        self.identity_registry = AssetIdentityRegistry.reviewed_defaults()
        self.candle_pipeline = OneMinuteCandlePipeline()
        self.microstructure = MicrostructureAccumulator()
        self._latest_trade_delta: dict[str, float] = {}
        self.rest_circuit = ProviderCircuitBreaker("bitunix_public_rest", "market")
        self.rest_bucket = TokenBucket(rate_per_second=8.0, capacity=8)
        self.coingecko_bucket = TokenBucket(rate_per_second=0.4, capacity=1)
        self.coingecko = CoinGeckoAdapter(default_coingecko_transport)
        # Optional keys are read from the process environment only; they are never persisted or logged.
        self.coinglass = CoinGlassProvider(api_key=os.environ.get("COINGLASS_API_KEY"))
        self.coinmarketcap = CoinMarketCapProvider(api_key=os.environ.get("COINMARKETCAP_API_KEY"))
        self.rss = RSSNewsAdapter(default_rss_transport)
        self._news_cache: dict[str, tuple[dict[str, Any], ...]] = {}
        self.logger: logging.Logger = logging.getLogger("traidr.live_service")

    async def run(self, *, run_once: bool = False) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = configure_service_logger(self.settings.service.resolved_log_path())
        self.logger.info("service_started")
        with DuckDBStore(self.database_path) as store:
            self._loop = asyncio.get_running_loop()
            initialize_schema(store.connection)
            repository = MarketRepository(store.connection)
            repository.seed_reviewed_identities()
            portfolio_payload, processed_keys = repository.load_paper_recovery()
            self.paper_simulator = PaperFuturesSimulator.from_persisted_portfolio(
                portfolio_payload,
                processed_idempotency_keys=processed_keys,
            )
            await self._refresh_universe(repository)
            if run_once:
                await self._analysis_cycle(repository)
                self._heartbeat(repository, "STOPPED", {"reason": "RUN_ONCE_COMPLETE"})
                self.logger.info("service_run_once_completed")
                return
            self._stream = BitunixPublicStream(self.active_symbols, intervals=("1m",))
            control_server = LocalControlServer(
                self.settings.service.bind_host,
                self.settings.service.control_port,
                self._enqueue_control,
            )
            control_server.start()
            tasks = (
                asyncio.create_task(self._stream.run(
                    lambda event: self._handle_event(repository, event),
                    self.stop_event,
                    health_handler=lambda status, reconnects, gaps, reasons: self._handle_stream_health(
                        repository, status, reconnects, gaps, reasons
                    ),
                )),
                asyncio.create_task(self._periodic_universe(repository)),
                asyncio.create_task(self._periodic_analysis(repository)),
                asyncio.create_task(self._periodic_heartbeat(repository)),
                asyncio.create_task(self._periodic_backup(repository)),
                asyncio.create_task(self._periodic_outcomes(repository)),
                asyncio.create_task(self._periodic_models(repository)),
                asyncio.create_task(self._periodic_news(repository)),
                asyncio.create_task(self._control_loop(repository)),
            )
            try:
                await self.stop_event.wait()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                control_server.stop()
                self._heartbeat(repository, "STOPPED", {"reason": "GRACEFUL_SHUTDOWN"})
                self.logger.info("service_stopped")

    def request_stop(self) -> None:
        self.stop_event.set()

    async def _refresh_universe(self, repository: MarketRepository) -> None:
        await self.rest_bucket.acquire()
        pairs_result = await self.adapter.fetch_trading_pairs()
        if not pairs_result.ok:
            self.active_symbols = self.settings.service.watchlist
            self.logger.warning("universe_refresh_degraded")
            self._heartbeat(repository, "DEGRADED", {"reasons": list(pairs_result.reason_codes)})
            return
        pairs = cast(list[BitunixTradingPair], pairs_result.value)
        for pair in pairs:
            repository.upsert_instrument(pair)
        ticker_symbols = tuple(pair.symbol for pair in pairs)
        ranked: list[BitunixTicker] = []
        for offset in range(0, len(ticker_symbols), 50):
            await self.rest_bucket.acquire()
            result = await self.adapter.fetch_tickers(ticker_symbols[offset : offset + 50])
            if result.ok:
                ranked.extend(cast(list[BitunixTicker], result.value))
        ranked.sort(key=lambda item: item.quote_volume, reverse=True)
        selected = list(self.settings.service.watchlist)
        selected.extend(item.symbol for item in ranked[: self.settings.service.detailed_stream_limit])
        self.active_symbols = tuple(dict.fromkeys(selected))[: self.settings.service.detailed_stream_limit]
        await self._bootstrap_active_candles(repository)
        self._heartbeat(
            repository,
            "HEALTHY",
            {"active_symbols": len(self.active_symbols), "discovered_pairs": len(pairs)},
        )
        self.logger.info("universe_refreshed")

    async def _analysis_cycle(self, repository: MarketRepository) -> None:
        if not self.active_symbols:
            return
        batch_size = self.settings.service.analysis_batch_size
        indexes = [(self._analysis_cursor + index) % len(self.active_symbols) for index in range(batch_size)]
        symbols = tuple(self.active_symbols[index] for index in indexes)
        self._analysis_cursor = (self._analysis_cursor + batch_size) % len(self.active_symbols)
        for symbol in symbols:
            await self.rest_bucket.acquire()
            funding_result = await self.adapter.fetch_funding_rate(symbol)
            await self.rest_bucket.acquire()
            depth_result = await self.adapter.fetch_depth(symbol, "15")
            funding = cast(BitunixFundingRate, funding_result.value) if funding_result.ok else None
            depth = cast(BitunixDepthSnapshot, depth_result.value) if depth_result.ok else None
            depth_imbalance, spread_bps = _depth_metrics(depth)
            basis_bps = _basis_bps(funding)
            mark_price = funding.mark_price if funding is not None else None
            instrument_id = f"bitunix:{symbol}"
            identity = self.identity_registry.resolve(
                source="bitunix",
                binding_kind="futures_symbol",
                source_identifier=symbol,
            )
            cross_market = await self._cross_market(identity.canonical_asset_id if identity else None, mark_price)
            external_context = await self._external_market_context(symbol, mark_price)
            if external_context:
                cross_market = {**(cross_market or {}), **external_context}
            if mark_price is not None and instrument_id in self.paper_simulator.positions:
                marked = self.paper_simulator.process_price(instrument_id, mark_price)
                if marked.ok and marked.value is not None:
                    repository.upsert_paper_position(marked.value)
                if funding is not None:
                    before = self.paper_simulator.positions[instrument_id]
                    funding_time = _funding_period(datetime.now(tz=UTC), funding.funding_interval_hours)
                    funded = (
                        self.paper_simulator.apply_funding(
                            instrument_id,
                            funding.funding_rate,
                            funding_time=funding_time,
                        )
                        if funding_time >= before.opened_at
                        else None
                    )
                    if funded is not None and funded.ok and funded.value is not None:
                        payment = funded.value.funding_paid_usd - before.funding_paid_usd
                        funding_key = f"{funded.value.position_id}|{funding_time.isoformat()}"
                        repository.record_paper_funding(
                            funding_event_id=f"funding:{funded.value.position_id}:{int(funding_time.timestamp())}",
                            position_id=funded.value.position_id,
                            funding_time=funding_time,
                            funding_rate=funding.funding_rate,
                            payment_usd=payment,
                            idempotency_key=funding_key,
                        )
                        repository.upsert_paper_position(funded.value)
            for horizon in self.settings.service.horizons:
                await self.rest_bucket.acquire()
                kline_result = await self.adapter.fetch_kline(symbol, horizon, 200)
                if not kline_result.ok:
                    self._record_rest_health(repository, symbol, MarketChannel.KLINE, "DEGRADED", kline_result.reason_codes)
                    continue
                candles = cast(list[BitunixCandle], kline_result.value)
                repository.upsert_candles(f"bitunix:{symbol}", horizon, candles)
                evidence_id = f"bitunix-rest:{symbol}:{horizon}:{candles[-1].time_ms}"
                feature_result = build_multi_horizon_features(
                    instrument_id=f"bitunix:{symbol}",
                    horizon=horizon,
                    candles=candles,
                    evidence_ids=(evidence_id,),
                    depth_imbalance=depth_imbalance,
                    spread_bps=spread_bps,
                    funding_rate=float(funding.funding_rate) if funding else None,
                    basis_bps=basis_bps,
                )
                if not feature_result.ok or feature_result.value is None:
                    continue
                feature = feature_result.value
                if repository.has_unresolved_gap(instrument_id):
                    feature = feature.model_copy(
                        update={
                            "data_coverage": min(feature.data_coverage, 0.50),
                            "contradiction_flags": (
                                *feature.contradiction_flags,
                                "UNRESOLVED_INGESTION_GAP",
                            ),
                            "quality_warnings": (*feature.quality_warnings, "DEPENDENT_STREAM_GAP"),
                        }
                    )
                repository.record_feature(feature)
                if horizon == "15m":
                    scanner_score = self._build_scanner_score(
                        symbol=symbol,
                        feature=feature,
                        candles=candles,
                        depth_imbalance=depth_imbalance,
                        funding=funding,
                        external_context=cross_market,
                        canonical_asset_id=identity.canonical_asset_id if identity else None,
                    )
                    repository.record_scanner_score(scanner_score)
                bundle = build_evidence_bundle(
                    feature,
                    canonical_asset_id=identity.canonical_asset_id if identity else None,
                    microstructure={
                        "depth_imbalance": depth_imbalance,
                        "spread_bps": spread_bps,
                    } if depth_imbalance is not None and spread_bps is not None else None,
                    futures_crowding={
                        "funding_rate": float(funding.funding_rate),
                        "basis_bps": basis_bps,
                    } if funding is not None else None,
                    cross_market=cross_market,
                    news=self._news_cache.get(identity.canonical_asset_id, ()) if identity else (),
                )
                repository.record_evidence_bundle(bundle)
                scored_feature = feature.model_copy(
                    update={
                        "data_coverage": bundle.data_coverage,
                        "missing_features": (*feature.missing_features, *bundle.missing_components),
                        "contradiction_flags": (
                            *feature.contradiction_flags,
                            *bundle.contradiction_flags,
                            *bundle.hard_vetoes,
                        ),
                        "evidence_ids": bundle.evidence_ids,
                    }
                )
                signal = score_directional_setup(scored_feature, token_safety_required=False)
                repository.record_signal(signal)
                portfolio = self.paper_simulator.snapshot()
                stress = assess_portfolio_stress(
                    portfolio,
                    self._paper_return_histories(repository),
                )
                repository.record_stress_snapshot(stress)
                risk = assess_paper_signal(
                    signal,
                    portfolio,
                    limits=self.paper_simulator.limits,
                    market_fresh=not feature.quality_warnings and not feature.contradiction_flags,
                    depth_available=depth is not None and spread_bps is not None,
                    mark_index_available=funding is not None
                    and funding.mark_price > 0
                    and funding.index_price > 0,
                    correlation_exposure_ok=stress.maximum_correlation <= 0.85,
                    simultaneous_loss_stress_ok=stress.approved,
                )
                repository.record_risk_assessment(risk)
                if self.paper_simulation_enabled and mark_price is not None:
                    paper_result = self.paper_simulator.open_from_signal(
                        signal,
                        mark_price=mark_price,
                        risk_approved=risk.outcome == "APPROVED_PAPER",
                        market_data_fresh=risk.limit_checks["market_fresh"],
                        depth_available=risk.limit_checks["depth_available"],
                        leverage=risk.approved_leverage,
                        manual_or_auto_paper_enabled=True,
                        available_depth_notional_usd=_depth_notional(depth),
                    )
                    if paper_result.ok and paper_result.value is not None:
                        repository.record_paper_execution(*paper_result.value)
                self._record_rest_health(repository, symbol, MarketChannel.KLINE, "HEALTHY", ("BITUNIX_REST_ANALYSIS_OK",))
        repository.record_portfolio(self.paper_simulator.snapshot())

    def _build_scanner_score(
        self,
        *,
        symbol: str,
        feature: FeatureSnapshot,
        candles: tuple[BitunixCandle, ...] | list[BitunixCandle],
        depth_imbalance: float | None,
        funding: BitunixFundingRate | None,
        external_context: dict[str, Any] | None,
        canonical_asset_id: str | None,
    ) -> ScannerScore:
        """Build a factor-auditable research score from available live evidence."""

        fields: dict[str, float] = {}
        sources: dict[str, str] = {}
        technical = feature.features
        trend = technical.get("trend_strength_pct")
        if trend is not None:
            fields["price_structure"] = max(-1.0, min(1.0, float(trend) / 1.5))
            sources["price_structure"] = "bitunix:multi_horizon"
        volume = sum((float(candle.quote_volume) for candle in candles[-96:]), 0.0)
        if volume > 0:
            fields["volume_24h_usd"] = volume
            sources["volume_24h_usd"] = "bitunix:candles"
        if depth_imbalance is not None:
            fields["order_book_imbalance"] = float(depth_imbalance)
            sources["order_book_imbalance"] = "bitunix:depth"
        trade_delta = self._latest_trade_delta.get(feature.instrument_id)
        if trade_delta is not None:
            fields["trade_delta"] = trade_delta
            sources["trade_delta"] = "bitunix:trades"
        if funding is not None:
            fields["funding_rate"] = float(funding.funding_rate)
            sources["funding_rate"] = "bitunix:funding"

        context = external_context or {}
        for field_name, context_keys, source in (
            ("funding_rate", ("coinglass_funding_rate",), "coinglass"),
            ("oi_change_pct", ("coinglass_oi_change_pct",), "coinglass"),
            ("liquidation_pressure", ("coinglass_liquidation_pressure",), "coinglass"),
            ("btc_eth_correlation", ("btc_eth_correlation",), "correlation:btc_eth"),
        ):
            if field_name in fields:
                continue
            value = next((context.get(key) for key in context_keys if isinstance(context.get(key), (int, float))), None)
            if value is not None:
                fields[field_name] = float(value)
                sources[field_name] = source

        news_rows = self._news_cache.get(canonical_asset_id or "", ())
        catalyst = next(
            (
                float(item["catalyst_score"])
                for item in news_rows
                if isinstance(item.get("catalyst_score"), (int, float))
            ),
            None,
        )
        if catalyst is not None:
            fields["news_catalyst"] = catalyst
            sources["news_catalyst"] = "rss:news_evidence"

        last_price = technical.get("last_price")
        support = technical.get("support")
        resistance = technical.get("resistance")
        if last_price is not None and support is not None and resistance is not None:
            downside = max(float(last_price) - float(support), 0.0)
            upside = max(float(resistance) - float(last_price), 0.0)
            if downside > 0:
                fields["risk_reward"] = upside / downside
                sources["risk_reward"] = "bitunix:structure"

        conflicts: list[str] = []
        for key in ("divergence_bps", "coinmarketcap_divergence_bps"):
            value = context.get(key)
            if isinstance(value, (int, float)) and abs(float(value)) > 100.0:
                conflicts.append(f"{key.upper()}_OVER_100_BPS")
        return score_scanner_input(
            ScannerInput(
                instrument_id=f"bitunix:{symbol}",
                fields=fields,
                field_sources=sources,
                observed_at=feature.observed_at,
                conflicts=tuple(conflicts),
                critical_conflict=bool(conflicts),
                volume_reference=None,
            )
        )

    def _paper_return_histories(self, repository: MarketRepository) -> dict[str, tuple[float, ...]]:
        histories: dict[str, tuple[float, ...]] = {}
        for position in self.paper_simulator.open_positions():
            candles = repository.load_recent_candles(position.instrument_id, "1h", limit=61)
            closes = [float(candle.close) for candle in candles]
            histories[position.instrument_id] = tuple(
                (current / previous - 1.0) * 100.0
                for previous, current in zip(closes, closes[1:], strict=True)
                if previous > 0
            )
        return histories

    async def _handle_event(self, repository: MarketRepository, event: MarketEvent) -> None:
        repository.record_market_event(event)
        if event.channel is MarketChannel.KLINE:
            try:
                candle, gap = self.candle_pipeline.ingest(event)
                repository.upsert_candles(event.instrument_id, "1m", (candle,), received_at=event.received_at)
                if gap is not None:
                    repository.upsert_ingestion_gap(gap)
                    await self._recover_gap(repository, gap)
                one_minute = repository.load_recent_candles(event.instrument_id, "1m", limit=1600)
                for horizon in self.settings.service.horizons:
                    aggregated = aggregate_candles(one_minute, horizon)
                    if aggregated:
                        repository.upsert_candles(event.instrument_id, horizon, aggregated[-2:])
            except (TypeError, ValueError):
                self._record_rest_health(
                    repository,
                    event.instrument_id.split(":", 1)[-1],
                    MarketChannel.KLINE,
                    "DEGRADED",
                    ("BITUNIX_WS_KLINE_MALFORMED",),
                )
        metric = self.microstructure.ingest(event)
        if metric is not None:
            self._latest_trade_delta[metric.instrument_id] = metric.trade_delta
            repository.record_microstructure(
                metric_id=metric.metric_id,
                instrument_id=metric.instrument_id,
                observed_at=metric.observed_at,
                bid_price=metric.bid_price,
                ask_price=metric.ask_price,
                spread_bps=metric.spread_bps,
                depth_imbalance=metric.depth_imbalance,
                trade_delta=metric.trade_delta,
                payload={
                    "absorption": metric.absorption,
                    "liquidity_concentration": metric.liquidity_concentration,
                    "resilience": metric.resilience,
                },
            )
        lag = event.age_seconds()
        freshness_limit = 120.0 if event.channel is MarketChannel.KLINE else 15.0
        health = DataHealth(
            source=event.source,
            instrument_id=event.instrument_id,
            channel=event.channel,
            status="HEALTHY" if lag <= freshness_limit else "DEGRADED",
            checked_at=datetime.now(tz=UTC),
            last_event_at=event.event_at,
            lag_seconds=lag,
            reconnect_count=self._stream.reconnect_count if self._stream else 0,
            gap_count=self._stream.gap_count if self._stream else 0,
            coverage=1.0 if event.quality.value == "sufficient" else 0.5,
            reason_codes=("PUBLIC_STREAM_FRESH",) if lag <= freshness_limit else ("PUBLIC_STREAM_LAGGING",),
        )
        repository.upsert_health(health)

    async def _bootstrap_active_candles(self, repository: MarketRepository) -> None:
        """Bound REST bootstrap so a large universe cannot fan out without control."""

        semaphore = asyncio.Semaphore(8)

        async def bootstrap(symbol: str) -> None:
            async with semaphore:
                await self.rest_bucket.acquire()
                if not self.rest_circuit.allow():
                    self._record_rest_health(
                        repository, symbol, MarketChannel.KLINE, "DOWN", ("BITUNIX_REST_CIRCUIT_OPEN",)
                    )
                    return
                result = await self.adapter.fetch_kline(symbol, "1m", 200)
                if not result.ok:
                    self.rest_circuit.failure()
                    repository.upsert_provider_circuit(self.rest_circuit.snapshot())
                    self._record_rest_health(repository, symbol, MarketChannel.KLINE, "DEGRADED", result.reason_codes)
                    return
                self.rest_circuit.success()
                repository.upsert_provider_circuit(self.rest_circuit.snapshot())
                candles = cast(list[BitunixCandle], result.value)
                instrument_id = f"bitunix:{symbol}"
                repository.upsert_candles(instrument_id, "1m", candles)
                for horizon in self.settings.service.horizons:
                    aggregated = aggregate_candles(candles, horizon)
                    if aggregated:
                        repository.upsert_candles(instrument_id, horizon, aggregated)

        await asyncio.gather(*(bootstrap(symbol) for symbol in self.active_symbols))

    async def _recover_gap(self, repository: MarketRepository, gap: IngestionGap) -> None:
        backfilling = gap.model_copy(
            update={
                "status": IngestionGapStatus.BACKFILLING,
                "attempts": gap.attempts + 1,
                "updated_at": datetime.now(tz=UTC),
                "reason_codes": (*gap.reason_codes, "REST_BACKFILL_STARTED"),
            }
        )
        repository.upsert_ingestion_gap(backfilling)
        symbol = gap.instrument_id.split(":", 1)[-1]
        await self.rest_bucket.acquire()
        result = await self.adapter.fetch_kline(symbol, "1m", 200)
        recovered = False
        if result.ok:
            candles = cast(list[BitunixCandle], result.value)
            repository.upsert_candles(gap.instrument_id, "1m", candles)
            expected = set(expected_one_minute_range(gap.gap_start, gap.gap_end))
            recovered = expected.issubset({candle.time_ms for candle in candles})
        final = backfilling.model_copy(
            update={
                "status": IngestionGapStatus.RESOLVED if recovered else IngestionGapStatus.UNRESOLVED,
                "updated_at": datetime.now(tz=UTC),
                "reason_codes": (
                    *backfilling.reason_codes,
                    "REST_BACKFILL_RESOLVED" if recovered else "REST_BACKFILL_INCOMPLETE_SIGNAL_VETO",
                ),
            }
        )
        repository.upsert_ingestion_gap(final)

    async def _handle_stream_health(
        self,
        repository: MarketRepository,
        status: str,
        reconnects: int,
        gaps: int,
        reasons: tuple[str, ...],
    ) -> None:
        now = datetime.now(tz=UTC)
        for symbol in self.active_symbols:
            repository.upsert_health(
                DataHealth(
                    source="bitunix_public_ws",
                    instrument_id=f"bitunix:{symbol}",
                    channel=MarketChannel.TICKER,
                    status=cast(Any, status),
                    checked_at=now,
                    reconnect_count=reconnects,
                    gap_count=gaps,
                    coverage=1.0 if status == "HEALTHY" else 0.0,
                    reason_codes=reasons,
                )
            )

    def _record_rest_health(
        self,
        repository: MarketRepository,
        symbol: str,
        channel: MarketChannel,
        status: str,
        reasons: tuple[str, ...],
    ) -> None:
        repository.upsert_health(
            DataHealth(
                source="bitunix_public_rest",
                instrument_id=f"bitunix:{symbol}",
                channel=channel,
                status=cast(Any, status),
                checked_at=datetime.now(tz=UTC),
                coverage=1.0 if status == "HEALTHY" else 0.0,
                reason_codes=reasons,
            )
        )

    async def _periodic_universe(self, repository: MarketRepository) -> None:
        while not self.stop_event.is_set():
            await self._wait(self.settings.service.universe_refresh_seconds)
            if not self.stop_event.is_set():
                await self._refresh_universe(repository)

    async def _periodic_analysis(self, repository: MarketRepository) -> None:
        while not self.stop_event.is_set():
            await self._analysis_cycle(repository)
            await self._wait(self.settings.service.analysis_cycle_seconds)

    async def _periodic_heartbeat(self, repository: MarketRepository) -> None:
        while not self.stop_event.is_set():
            self._heartbeat(repository, "RUNNING", {"active_symbols": len(self.active_symbols)})
            await self._wait(self.settings.service.heartbeat_seconds)

    async def _periodic_backup(self, repository: MarketRepository) -> None:
        while not self.stop_event.is_set():
            await self._wait(self.settings.service.backup_interval_seconds)
            if not self.stop_event.is_set():
                repository.apply_retention()
                self._create_backup(repository)

    async def _periodic_outcomes(self, repository: MarketRepository) -> None:
        while not self.stop_event.is_set():
            label_expired_signals(repository.connection)
            await self._wait(self.settings.service.outcome_label_seconds)

    async def _periodic_models(self, repository: MarketRepository) -> None:
        while not self.stop_event.is_set():
            await self._wait(self.settings.service.model_training_seconds)
            if not self.stop_event.is_set():
                train_eligible_buckets(
                    repository.connection,
                    artifact_root=self.settings.service.resolved_model_directory(),
                )

    async def _periodic_news(self, repository: MarketRepository) -> None:
        while not self.stop_event.is_set():
            for source, url in ALLOWLISTED_RSS_FEEDS.items():
                result = await asyncio.to_thread(self.rss.fetch, url)
                rows = [item.to_dict() for item in result.items]
                evidence = map_news_evidence(
                    rows,
                    source=source,
                    registry=self.identity_registry,
                )
                for item in evidence:
                    repository.record_news_evidence(item)
                    asset_id = item.get("canonical_asset_id")
                    if asset_id:
                        existing = self._news_cache.get(str(asset_id), ())
                        self._news_cache[str(asset_id)] = tuple((item, *existing))[:50]
            await self._wait(900)

    async def _external_market_context(
        self,
        symbol: str,
        futures_price: Decimal | None,
    ) -> dict[str, Any] | None:
        """Collect optional read-only derivatives and market context for evidence."""

        context: dict[str, Any] = {}
        coinglass = await self.coinglass.fetch(symbol)
        if coinglass.ok and coinglass.value is not None:
            for key in (
                "funding_rate",
                "open_interest",
                "oi_change_pct",
                "liquidation_pressure",
                "long_short_ratio",
            ):
                value = coinglass.value.fields.get(key)
                if value is not None:
                    context[f"coinglass_{key}"] = value
            context["coinglass_observed_at"] = coinglass.value.observed_at.isoformat()
        elif coinglass.reason_codes:
            context["coinglass_reason_codes"] = list(coinglass.reason_codes)

        coinmarketcap = await self.coinmarketcap.fetch(symbol)
        if coinmarketcap.ok and coinmarketcap.value is not None:
            for key in ("price_usd", "market_cap_usd", "volume_24h_usd", "percent_change_24h"):
                value = coinmarketcap.value.fields.get(key)
                if value is not None:
                    context[f"coinmarketcap_{key}"] = value
            cmc_price = coinmarketcap.value.fields.get("price_usd")
            if futures_price is not None and isinstance(cmc_price, (int, float)) and cmc_price > 0:
                context["coinmarketcap_divergence_bps"] = float(
                    (futures_price - Decimal(str(cmc_price))) / Decimal(str(cmc_price)) * Decimal("10000")
                )
            context["coinmarketcap_observed_at"] = coinmarketcap.value.observed_at.isoformat()
        elif coinmarketcap.reason_codes:
            context["coinmarketcap_reason_codes"] = list(coinmarketcap.reason_codes)

        return context or None

    async def _cross_market(
        self,
        canonical_asset_id: str | None,
        futures_price: Decimal | None,
    ) -> dict[str, Any] | None:
        if canonical_asset_id is None or futures_price is None or futures_price <= 0:
            return None
        bindings = [
            binding
            for binding in self.identity_registry.bindings_for(canonical_asset_id)
            if binding.source == "coingecko" and binding.binding_kind == "spot_id"
        ]
        if len(bindings) != 1:
            return None
        await self.coingecko_bucket.acquire()
        result = await asyncio.to_thread(self.coingecko.fetch_snapshot, bindings[0].source_identifier)
        if not result.ok or result.value is None:
            return None
        spot = result.value.metrics.price_usd
        divergence_bps = float((futures_price - spot) / spot * Decimal("10000")) if spot > 0 else None
        return {
            "source": "coingecko_keyless",
            "spot_price_usd": str(spot),
            "futures_price_usd": str(futures_price),
            "divergence_bps": divergence_bps,
            "observed_at": result.value.freshness.observed_at.isoformat(),
            "reason_codes": ("EXACT_SOURCE_BINDING", "CROSS_MARKET_CONTEXT_ONLY"),
        }

    def _create_backup(self, repository: MarketRepository) -> Path:
        """Checkpoint and copy the database while this single writer owns the loop."""

        repository.connection.execute("CHECKPOINT")
        backup_directory = self.settings.service.resolved_backup_directory().resolve()
        backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        destination = (backup_directory / f"traidr-{timestamp}.duckdb").resolve()
        if destination.parent != backup_directory:
            raise ValueError("backup target escaped configured directory")
        database_row = repository.connection.execute("SELECT current_database()").fetchone()
        if database_row is None:
            raise RuntimeError("DuckDB did not report the current database")
        source_name = str(database_row[0])
        quoted_source = source_name.replace('"', '""')
        quoted_destination = str(destination).replace("'", "''")
        repository.connection.execute(f"ATTACH '{quoted_destination}' AS traidr_backup")
        try:
            repository.connection.execute(
                f'COPY FROM DATABASE "{quoted_source}" TO traidr_backup'
            )
        finally:
            repository.connection.execute("DETACH traidr_backup")
        cutoff = datetime.now(tz=UTC) - timedelta(days=self.settings.service.backup_retention_days)
        for candidate in backup_directory.glob("traidr-*.duckdb"):
            resolved = candidate.resolve()
            if resolved.parent != backup_directory or resolved == destination:
                continue
            modified = datetime.fromtimestamp(resolved.stat().st_mtime, tz=UTC)
            if modified < cutoff:
                resolved.unlink()
        self.logger.info("database_backup_completed")
        return destination

    def _enqueue_control(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._loop is None:
            return {"status": "UNAVAILABLE", "can_execute_trades": False}
        request_id = f"control-{uuid4().hex}"
        idempotency_key = str(payload.get("idempotency_key") or request_id)
        self._loop.call_soon_threadsafe(
            self._control_queue.put_nowait,
            (request_id, action, {**payload, "idempotency_key": idempotency_key}),
        )
        return {"status": "ACCEPTED", "request_id": request_id, "can_execute_trades": False}

    async def _control_loop(self, repository: MarketRepository) -> None:
        while not self.stop_event.is_set():
            request_id, action, payload = await self._control_queue.get()
            idempotency_key = str(payload.pop("idempotency_key"))
            if not repository.record_control_request(
                request_id=request_id,
                idempotency_key=idempotency_key,
                action=action,
                payload=payload,
            ):
                continue
            try:
                if action == "refresh":
                    await self._analysis_cycle(repository)
                    result = {"refreshed": True}
                elif action == "paper_enable":
                    self.paper_simulation_enabled = True
                    result = {"paper_simulation_enabled": True, "live_trading_enabled": False}
                elif action == "paper_disable":
                    self.paper_simulation_enabled = False
                    result = {"paper_simulation_enabled": False, "live_trading_enabled": False}
                else:
                    raise ValueError("unsupported control action")
                repository.complete_control_request(request_id, status="COMPLETED", result=result)
                self.logger.info("control_request_completed", extra={"correlation_id": request_id})
            except Exception:
                self.logger.error("control_request_failed", extra={"correlation_id": request_id})
                repository.complete_control_request(
                    request_id,
                    status="FAILED",
                    result={"reason_codes": ["CONTROL_REQUEST_FAILED"]},
                )

    async def _wait(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=seconds)
        except TimeoutError:
            pass

    def _heartbeat(self, repository: MarketRepository, status: str, details: dict[str, Any]) -> None:
        repository.heartbeat(
            service_name="traidr-live-research",
            started_at=self.started_at,
            status=status,
            data_mode=self.settings.profile.data_mode.value,
            details={**details, "can_execute_trades": False},
        )


def _depth_metrics(depth: BitunixDepthSnapshot | None) -> tuple[float | None, float | None]:
    if depth is None or not depth.bids or not depth.asks:
        return None, None
    delta = depth.depth_delta()
    imbalance = float(delta.depth_delta_percent / Decimal("50") - Decimal("1"))
    bid = depth.bids[0].price
    ask = depth.asks[0].price
    midpoint = (bid + ask) / Decimal("2")
    spread = float((ask - bid) / midpoint * Decimal("10000")) if midpoint > 0 else None
    return imbalance, spread


def _basis_bps(funding: BitunixFundingRate | None) -> float | None:
    if funding is None or funding.index_price <= 0:
        return None
    return float((funding.mark_price - funding.index_price) / funding.index_price * Decimal("10000"))


def _depth_notional(depth: BitunixDepthSnapshot | None) -> Decimal | None:
    if depth is None:
        return None
    return sum((level.price * level.amount for level in (*depth.bids, *depth.asks)), Decimal("0"))


def _funding_period(reference: datetime, interval_hours: int) -> datetime:
    seconds = max(1, interval_hours) * 3600
    timestamp = int(reference.astimezone(UTC).timestamp())
    return datetime.fromtimestamp(timestamp // seconds * seconds, tz=UTC)
