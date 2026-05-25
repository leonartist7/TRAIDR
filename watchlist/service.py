"""Local watchlist service with read-only scan alerts."""

from __future__ import annotations

from datetime import datetime, timezone

from data_pipeline.live_market_loader import LiveMarketLoader
from data_pipeline.market_scan import real_dexscreener_loader, scan_markets
from notifications.history import AlertHistory
from notifications.models import Alert, AlertSeverity, SendResult
from radar.scan_to_radar import scan_candidates_to_radar
from storage.repositories import IntelligenceRepository, ResearchRepository
from watchlist.models import WatchEntry, WatchScanRecord, WatchScanResult
from watchlist.repository import WatchlistRepository

_RISK_DELTA_ALERT = 15.0
_OPPORTUNITY_DELTA_ALERT = 15.0


class WatchlistService:
    def __init__(
        self,
        watchlist_repository: WatchlistRepository,
        *,
        research_repository: ResearchRepository | None = None,
        intelligence_repository: IntelligenceRepository | None = None,
        loader: LiveMarketLoader | None = None,
        source_names: tuple[str, ...] = ("dexscreener",),
    ) -> None:
        self.watchlist_repository = watchlist_repository
        self.research_repository = research_repository
        self.intelligence_repository = intelligence_repository
        self.loader = loader
        self.source_names = source_names

    def add(
        self,
        pair_ref: str,
        *,
        note: str = "",
        tags: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> WatchEntry:
        return self.watchlist_repository.upsert_entry(
            pair_ref=pair_ref,
            note=note,
            tags=tags,
            created_at=now,
        )

    def remove(self, pair_ref: str) -> bool:
        return self.watchlist_repository.deactivate_entry(pair_ref)

    def list(self) -> tuple[WatchEntry, ...]:
        return self.watchlist_repository.list_entries(active_only=True)

    def scan(self, *, now: datetime | None = None) -> WatchScanResult:
        scan_time = now or datetime.now(timezone.utc)
        entries = self.watchlist_repository.list_entries(active_only=True)
        if not entries:
            return WatchScanResult(
                status="INSUFFICIENT_DATA",
                scanned=(),
                alerts_created=(),
                reason_codes=("WATCHLIST_EMPTY",),
            )

        records: list[WatchScanRecord] = []
        alerts: list[str] = []
        loader = self.loader or real_dexscreener_loader(now=scan_time)
        for entry in entries:
            previous = self.watchlist_repository.latest_scan_for(entry.pair_ref)
            record = self._scan_entry(entry, loader=loader, now=scan_time)
            self.watchlist_repository.record_scan_result(record)
            records.append(record)
            alerts.extend(self._record_alerts(entry, previous, record, now=scan_time))
        return WatchScanResult(
            status="OK" if records else "INSUFFICIENT_DATA",
            scanned=tuple(records),
            alerts_created=tuple(alerts),
            reason_codes=("WATCHLIST_SCAN_COMPLETE",),
        )

    def _scan_entry(
        self,
        entry: WatchEntry,
        *,
        loader: LiveMarketLoader,
        now: datetime,
    ) -> WatchScanRecord:
        result = scan_markets(
            pair_refs=(entry.pair_ref,),
            source_names=self.source_names,
            loader=loader,
            now=now,
            repository=self.research_repository,
        )
        if not result.candidates:
            return WatchScanRecord(
                pair_ref=entry.pair_ref,
                scanned_at=now,
                status="INSUFFICIENT_DATA",
                radar_state="AVOID",
                opportunity_score=0.0,
                risk_score=100.0,
                reason_codes=result.reason_codes,
            )
        candidate = result.candidates[0]
        radar = scan_candidates_to_radar((candidate,))
        if not radar:
            return WatchScanRecord(
                pair_ref=entry.pair_ref,
                scanned_at=now,
                status="INSUFFICIENT_DATA",
                radar_state="AVOID",
                opportunity_score=0.0,
                risk_score=100.0,
                reason_codes=("WATCHLIST_RADAR_MISSING",),
            )
        top = radar[0]
        return WatchScanRecord(
            pair_ref=entry.pair_ref,
            scanned_at=now,
            status="OK",
            radar_state=top.state.value,
            opportunity_score=top.opportunity_score,
            risk_score=top.risk_score,
            reason_codes=top.reason_codes,
        )

    def _record_alerts(
        self,
        entry: WatchEntry,
        previous: WatchScanRecord | None,
        current: WatchScanRecord,
        *,
        now: datetime,
    ) -> tuple[str, ...]:
        if previous is None or self.intelligence_repository is None:
            return ()
        history = AlertHistory(self.intelligence_repository)
        created: list[str] = []
        if current.risk_score - previous.risk_score >= _RISK_DELTA_ALERT:
            alert = Alert(
                subject_id=entry.pair_ref,
                state=current.radar_state,
                severity=AlertSeverity.WARNING,
                reason_codes=("WATCH_RISK_WORSENED",),
                message=f"{entry.pair_ref} risk worsened from {previous.risk_score:.1f} to {current.risk_score:.1f}.",
            )
            created.append(
                history.record(
                    alert,
                    SendResult("local", "RECORDED_ONLY", ("LOCAL_ONLY", "NO_EXECUTION_ACTION")),
                    recorded_at=now,
                )
            )
        if current.opportunity_score - previous.opportunity_score >= _OPPORTUNITY_DELTA_ALERT:
            alert = Alert(
                subject_id=entry.pair_ref,
                state=current.radar_state,
                severity=AlertSeverity.INFO,
                reason_codes=("WATCH_OPPORTUNITY_IMPROVED",),
                message=(
                    f"{entry.pair_ref} opportunity improved from "
                    f"{previous.opportunity_score:.1f} to {current.opportunity_score:.1f}."
                ),
            )
            created.append(
                history.record(
                    alert,
                    SendResult("local", "RECORDED_ONLY", ("LOCAL_ONLY", "NO_EXECUTION_ACTION")),
                    recorded_at=now,
                )
            )
        return tuple(created)
