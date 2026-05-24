import pytest

from agents.cio_agent import CIOAgent
from agents.technical_agent import TechnicalAgent
from agents.token_safety_agent import TokenSafetyAgent
from agents.agent_bus import run_agent_bus
from intelligence.macro_regime import score_macro_regime
from notifications.history import AlertHistory
from notifications.models import Alert, AlertSeverity, SendResult
from radar.opportunity_radar import rank_watchlist
from scheduler.reports import build_research_report
from scheduler.research_scheduler import ResearchScheduler
from storage.repositories import IntelligenceRepository, RepositoryWriteError


def test_intelligence_outputs_persist_to_duckdb(duckdb_store, now) -> None:
    repository = IntelligenceRepository(duckdb_store.connection)
    bus = run_agent_bus(
        [TechnicalAgent(), TokenSafetyAgent()],
        {"technical_momentum": 0.8, "token_safety_clear": True},
    )
    for analysis in bus.analyses:
        repository.record_agent_analysis(
            agent_name=str(analysis["agent"]),
            subject_id="fixture-sol-usdc",
            status=str(analysis["status"]),
            confidence=float(analysis["confidence"]),
            reason_codes=tuple(analysis["reason_codes"]),
            payload=analysis,
            recorded_at=now,
        )
    decision = CIOAgent().decide(bus.analyses)
    repository.record_cio_decision(
        subject_id="fixture-sol-usdc",
        recommendation=decision.recommendation.value,
        confidence=decision.ranking.confidence,
        reason_codes=decision.reason_codes,
        payload=decision.to_dict(),
        recorded_at=now,
    )
    macro = score_macro_regime({"risk_appetite": 0.7, "liquidity": 0.8})
    repository.record_macro_news_event(
        event_type="macro_regime",
        subject_id="market",
        classification=macro.classification,
        confidence=macro.confidence,
        reason_codes=macro.reason_codes,
        payload=macro.to_dict(),
        recorded_at=now,
    )
    radar = rank_watchlist([{"subject_id": "fixture-sol-usdc", "analyses": bus.analyses}])[0]
    repository.record_radar_state(
        subject_id=radar.subject_id,
        state=radar.state.value,
        rank=radar.rank,
        opportunity_score=radar.opportunity_score,
        risk_score=radar.risk_score,
        confidence=radar.confidence,
        reason_codes=radar.reason_codes,
        payload=radar.to_dict(),
        recorded_at=now,
    )
    alert = Alert("fixture-sol-usdc", radar.state.value, AlertSeverity.INFO, radar.reason_codes, "Research alert")
    AlertHistory(repository).record(
        alert,
        SendResult("local", "RECORDED_ONLY", ("LOCAL_HISTORY_ONLY",)),
        recorded_at=now,
    )
    scheduler = ResearchScheduler(
        repository=repository,
        handlers={"watchlist_check": lambda _context: {"status": "OK", "reason_codes": ["WATCHLIST_CHECKED"]}},
    )
    scheduler.run_due_tasks(
        now=now,
        context={},
        last_runs={task.name: now for task in scheduler.tasks if task.name != "watchlist_check"},
    )
    report = build_research_report(report_type="daily", radar_states=[radar.to_dict()])
    repository.record_research_report(
        report_type="daily",
        status=str(report["status"]),
        reason_codes=("REPORT_GENERATED",),
        payload=report,
        recorded_at=now,
    )

    counts = duckdb_store.connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM agent_analyses),
            (SELECT COUNT(*) FROM cio_decisions),
            (SELECT COUNT(*) FROM macro_news_events),
            (SELECT COUNT(*) FROM opportunity_radar_states),
            (SELECT COUNT(*) FROM notification_alerts),
            (SELECT COUNT(*) FROM scheduler_runs),
            (SELECT COUNT(*) FROM research_reports)
        """
    ).fetchone()
    assert counts == (2, 1, 1, 1, 1, 1, 1)


def test_intelligence_repository_rejects_secret_like_payload(duckdb_store, now) -> None:
    repository = IntelligenceRepository(duckdb_store.connection)

    with pytest.raises(RepositoryWriteError):
        repository.record_agent_analysis(
            agent_name="macro",
            subject_id="market",
            status="OK",
            confidence=0.1,
            reason_codes=("BAD_PAYLOAD",),
            payload={"api_key": "do-not-store"},
            recorded_at=now,
        )

