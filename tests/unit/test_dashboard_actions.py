from pathlib import Path

from dashboard.actions import run_dashboard_action
from storage.duckdb_store import DuckDBStore
from storage.schema import list_tables


def test_dashboard_daily_workflow_button_runs_local_research(tmp_path: Path) -> None:
    database = tmp_path / "dashboard-actions.duckdb"

    result = run_dashboard_action("daily_run", database=str(database))

    assert result.exit_code == 0
    assert result.can_execute_trades is False
    assert "TRAIDR Daily Run" in result.output
    assert database.exists()
    with DuckDBStore(database, read_only=True) as store:
        assert "research_reports" in list_tables(store.connection)


def test_dashboard_paper_simulation_button_is_simulation_only(tmp_path: Path) -> None:
    database = tmp_path / "dashboard-paper.duckdb"

    result = run_dashboard_action("paper_simulation", database=str(database))

    assert result.exit_code == 0
    assert result.can_execute_trades is False
    assert "TRAIDR Simulation" in result.output
    assert "mode: simulation" in result.output


def test_dashboard_unknown_action_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "dashboard-unknown.duckdb"

    result = run_dashboard_action("withdraw", database=str(database))

    assert result.exit_code == 2
    assert result.can_execute_trades is False
    assert "Unsupported dashboard action" in result.output
    assert not database.exists()
