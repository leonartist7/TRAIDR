from pathlib import Path

from cli.commands import (
    alerts,
    briefing,
    dashboard,
    discover,
    inspect,
    radar,
    scan,
    report,
    scheduler_once,
    simulate,
    status,
    token_detail,
)
from cli.main import main
from notifications.models import Alert, AlertSeverity, SendResult
from notifications.history import AlertHistory
from storage.duckdb_store import DuckDBStore
from storage.repositories import IntelligenceRepository
from storage.schema import initialize_schema


def test_status_reports_simulation_only_boundary(tmp_path: Path) -> None:
    result = status(str(tmp_path / "missing.duckdb"))

    assert result.exit_code == 0
    assert "mode: simulation" in result.output
    assert "live_trading: False" in result.output
    assert "withdrawals: False" in result.output


def test_simulate_uses_existing_paper_simulation_path(tmp_path: Path) -> None:
    database = tmp_path / "cli-sim.duckdb"

    result = simulate(str(database))

    assert result.exit_code == 0
    assert "Mode" not in result.output
    assert "mode: simulation only" in result.output
    assert "execution: FILLED" in result.output
    assert database.exists()


def test_inspect_shows_tables_after_simulation(tmp_path: Path) -> None:
    database = tmp_path / "cli-inspect.duckdb"
    simulate(str(database))

    result = inspect(str(database), limit=2)

    assert result.exit_code == 0
    assert "simulated_orders" in result.output
    assert "audit_events" in result.output


def test_radar_uses_fixture_when_db_has_no_radar(tmp_path: Path) -> None:
    result = radar(str(tmp_path / "empty.duckdb"), fixture=True)

    assert result.exit_code == 0
    assert "fixture-sol-usdc" in result.output
    assert "BUY_CANDIDATE" in result.output


def test_scan_fixture_outputs_candidates_and_radar(tmp_path: Path) -> None:
    database = tmp_path / "cli-scan.duckdb"

    result = scan(str(database), fixture=True)

    assert result.exit_code == 0
    assert "Market Scan" in result.output
    assert "fixture-sol-usdc" in result.output
    assert "can_execute_trades" in result.output
    assert database.exists()


def test_radar_reads_scan_evidence_from_database(tmp_path: Path) -> None:
    database = tmp_path / "cli-scan-radar.duckdb"
    scan(str(database), fixture=True)

    result = radar(str(database))

    assert result.exit_code == 0
    assert "source: scan_evidence" in result.output
    assert "fixture-sol-usdc" in result.output
    assert "can_execute_trades" in result.output


def test_scan_real_mode_without_sources_has_no_candidates(tmp_path: Path) -> None:
    result = scan(str(tmp_path / "scan-empty.duckdb"), pair_refs=("token-a",))

    assert result.exit_code == 0
    assert "No candidates found." in result.output
    assert "INSUFFICIENT_DATA" in result.output


def test_discover_fixture_outputs_candidates_and_radar(tmp_path: Path) -> None:
    database = tmp_path / "cli-discovery.duckdb"

    result = discover(str(database), fixture=True)

    assert result.exit_code == 0
    assert "Token Discovery" in result.output
    assert "fixture-sol-usdc" in result.output
    assert "can_execute_trades" in result.output
    assert database.exists()


def test_discover_real_mode_transport_failure_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "cli.commands.default_dexscreener_discovery_transport",
        lambda _limit: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    result = discover(source="dexscreener")

    assert result.exit_code == 0
    assert "INSUFFICIENT_DATA" in result.output
    assert "No candidates found." in result.output


def test_token_detail_fixture_outputs_research_card() -> None:
    result = token_detail(fixture=True)

    assert result.exit_code == 0
    assert "Token Detail" in result.output
    assert "fixture-sol-usdc" in result.output
    assert "can_execute_trades: False" in result.output


def test_briefing_missing_database_is_helpful(tmp_path: Path) -> None:
    result = briefing(str(tmp_path / "missing-briefing.duckdb"))

    assert result.exit_code == 0
    assert "Daily Briefing" in result.output
    assert "INSUFFICIENT_DATA" in result.output
    assert "Next Commands" in result.output


def test_report_reads_research_reports_after_scheduler_once(tmp_path: Path) -> None:
    database = tmp_path / "cli-scheduler.duckdb"

    scheduler_result = scheduler_once(str(database))
    report_result = report(str(database), report_type="daily")

    assert scheduler_result.exit_code == 0
    assert "tasks_run:" in scheduler_result.output
    assert report_result.exit_code == 0
    assert "daily" in report_result.output


def test_alerts_shows_local_alert_history(tmp_path: Path) -> None:
    database = tmp_path / "cli-alerts.duckdb"
    with DuckDBStore(database) as store:
        initialize_schema(store.connection)
        repository = IntelligenceRepository(store.connection)
        alert = Alert("token-a", "ALERT", AlertSeverity.WARNING, ("LOCAL_TEST",), "Alert token-a")
        AlertHistory(repository).record(
            alert,
            SendResult("local", "RECORDED_ONLY", ("LOCAL_ONLY",)),
        )

    result = alerts(str(database))

    assert result.exit_code == 0
    assert "token-a" in result.output
    assert "RECORDED_ONLY" in result.output


def test_dashboard_prints_launch_command_without_launching(tmp_path: Path) -> None:
    result = dashboard(str(tmp_path / "dash.duckdb"))

    assert result.exit_code == 0
    assert "python -m streamlit run dashboard/app.py" in result.output
    assert "manual for safety" in result.output


def test_main_dispatches_status(capsys) -> None:
    exit_code = main(["status"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "TRAIDR Status" in output


def test_main_accepts_database_after_subcommand(tmp_path: Path, capsys) -> None:
    exit_code = main(["status", "--database", str(tmp_path / "operator.duckdb")])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "operator.duckdb" in output
