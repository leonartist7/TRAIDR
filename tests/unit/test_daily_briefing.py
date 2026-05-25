from datetime import datetime, timezone
from decimal import Decimal

from cli.commands import briefing
from reports.daily_briefing import build_daily_briefing, empty_daily_briefing
from reports.formatters import format_daily_briefing
from reports.report_models import BriefingState
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository, ResearchRepository, SimulationRepository
from storage.schema import initialize_schema

NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_empty_daily_briefing_is_helpful_and_non_executing() -> None:
    report = empty_daily_briefing(now=NOW)
    output = format_daily_briefing(report)

    assert report.state is BriefingState.INSUFFICIENT_DATA
    assert report.can_execute_trades is False
    assert "python -m cli.main scan --fixture" in output
    assert "This briefing is read-only research" in output


def test_daily_briefing_reads_duckdb_sections(tmp_path) -> None:
    database = tmp_path / "briefing.duckdb"
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        _seed_briefing_data(store.connection)
        report = build_daily_briefing(store.connection, now=NOW)

    assert report.state is BriefingState.RISK_ON
    assert report.market_scan_summary["total_candidates"] == 1
    assert report.top_radar_candidates[0]["subject_id"] == "fixture-sol-usdc"
    assert report.new_alerts[0]["subject_id"] == "fixture-sol-usdc"
    assert report.recent_simulation_results[0]["pair_id"] == "fixture-sol-usdc"
    assert report.current_safety_status["can_execute_trades"] is False
    assert report.suggested_watchlist == ("fixture-sol-usdc",)


def test_daily_briefing_risk_off_for_high_risk_candidate(tmp_path) -> None:
    database = tmp_path / "risk-off.duckdb"
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        research = ResearchRepository(store.connection)
        research.record_evidence(
            source_name="market_scan:fixture",
            observed_at=NOW,
            quality_status="sufficient",
            payload={"pair_id": "risky-pair", "source": "fixture", "can_execute_trades": False},
            provenance={"source": "fixture", "pair_id": "risky-pair", "can_execute_trades": False},
            collected_at=NOW,
        )
        intelligence = IntelligenceRepository(store.connection)
        intelligence.record_radar_state(
            subject_id="risky-pair",
            state="AVOID",
            rank=1,
            opportunity_score=10.0,
            risk_score=90.0,
            confidence=0.8,
            reason_codes=("HIGH_RISK_SIGNAL_PRESENT",),
            payload={"can_execute_trades": False},
            recorded_at=NOW,
        )
        report = build_daily_briefing(store.connection, now=NOW)

    assert report.state is BriefingState.RISK_OFF
    assert report.highest_risk_candidates[0]["risk_score"] == 90.0


def test_cli_briefing_handles_missing_database(tmp_path) -> None:
    result = briefing(str(tmp_path / "missing.duckdb"))

    assert result.exit_code == 0
    assert "INSUFFICIENT_DATA" in result.output
    assert "Next Commands" in result.output


def _seed_briefing_data(connection) -> None:
    research = ResearchRepository(connection)
    research.record_evidence(
        source_name="market_scan:fixture",
        observed_at=NOW,
        quality_status="sufficient",
        payload={"pair_id": "fixture-sol-usdc", "source": "fixture", "can_execute_trades": False},
        provenance={"source": "fixture", "pair_id": "fixture-sol-usdc", "can_execute_trades": False},
        collected_at=NOW,
    )
    intelligence = IntelligenceRepository(connection)
    intelligence.record_radar_state(
        subject_id="fixture-sol-usdc",
        state="BUY_CANDIDATE",
        rank=1,
        opportunity_score=77.0,
        risk_score=20.0,
        confidence=0.7,
        reason_codes=("BUY_CANDIDATE_RESEARCH_ONLY",),
        payload={"can_execute_trades": False},
        recorded_at=NOW,
    )
    intelligence.record_notification_alert(
        subject_id="fixture-sol-usdc",
        channel="local",
        severity="INFO",
        fingerprint="fixture-alert",
        status="RECORDED_ONLY",
        reason_codes=("LOCAL_ONLY",),
        payload={"can_execute_trades": False},
        recorded_at=NOW,
    )
    simulation = SimulationRepository(connection)
    order_id = simulation.record_order(
        risk_decision_id="risk_fixture",
        side="BUY",
        pair_id="fixture-sol-usdc",
        notional_usd=Decimal("5"),
        order_status="FILLED",
        metadata={"can_execute_trades": False},
        created_at=NOW,
    )
    simulation.record_fill(
        order_id=order_id,
        quantity=Decimal("1"),
        price_usd=Decimal("5"),
        notional_usd=Decimal("5"),
        metadata={"can_execute_trades": False},
        filled_at=NOW,
    )
