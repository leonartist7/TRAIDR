from datetime import datetime, timezone
from pathlib import Path

from dashboard.queries import DashboardData
from dashboard.view_models import (
    build_command_cards,
    build_daily_mission,
    build_dashboard_health,
    summarize_action_output,
)


def test_dashboard_view_models_expose_non_executing_command_cards() -> None:
    cards = build_command_cards()

    assert [card.action for card in cards] == [
        "daily_run",
        "fixture_scan",
        "paper_simulation",
        "alerts_test",
        "scheduler_once",
        "status",
    ]
    assert all("trade" not in card.button_label.lower() for card in cards)


def test_daily_mission_reflects_missing_and_completed_local_evidence(tmp_path: Path) -> None:
    missing = _data(tmp_path / "missing.duckdb", exists=False)
    completed = _data(
        tmp_path / "ready.duckdb",
        exists=True,
        market_radar=[{"subject_id": "fixture-sol-usdc"}],
        alerts=[{"alert_id": "a1"}],
        portfolio_entries=[{"entry_id": "p1"}],
        reports=[{"report_id": "r1"}],
    )

    assert build_daily_mission(missing)[1].state == "missing"
    states = [item.state for item in build_daily_mission(completed)]
    assert states.count("complete") == 4


def test_dashboard_health_and_action_summary_are_operator_friendly(tmp_path: Path) -> None:
    data = _data(tmp_path / "local.duckdb", exists=True, tables={"audit_events", "research_reports"})
    health = build_dashboard_health(data)
    output = """
    TRAIDR Simulation
    mode: simulation
    database: local.duckdb
    execution: OK
    can_execute_trades: false
    noisy line
    """

    assert health.database_label == "Connected"
    assert health.table_count == 2
    assert summarize_action_output(output) == (
        "mode: simulation",
        "database: local.duckdb",
        "execution: OK",
        "can_execute_trades: false",
    )


def _data(
    path: Path,
    *,
    exists: bool,
    tables: set[str] | None = None,
    market_radar: list[dict] | None = None,
    alerts: list[dict] | None = None,
    portfolio_entries: list[dict] | None = None,
    reports: list[dict] | None = None,
) -> DashboardData:
    now = datetime(2026, 6, 26, tzinfo=timezone.utc)
    return DashboardData(
        database_path=path,
        database_exists=exists,
        tables=tables or set(),
        market_snapshots=[],
        market_radar=market_radar or [],
        scan_evidence=[],
        token_details=[],
        watchlist_entries=[],
        portfolio_entries=portfolio_entries or [],
        alerts=alerts or [],
        reports=reports or [],
        technical_vectors=[],
        anti_rug_status=[],
        risk_decisions=[],
        simulated_orders=[],
        simulated_fills=[],
        audit_events=[],
        safety_status={
            "runtime_mode": "simulation",
            "live_trading_implemented": False,
            "withdrawals_implemented": False,
            "llm_direct_order_execution_allowed": False,
            "created_at": now.isoformat(),
        },
    )
