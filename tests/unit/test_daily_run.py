from pathlib import Path

from cli.commands import daily_run
from cli.main import main
from storage.duckdb_store import DuckDBStore
from storage.schema import list_tables


def test_daily_run_creates_local_research_report(tmp_path: Path) -> None:
    database = tmp_path / "daily-run.duckdb"

    result = daily_run(str(database))

    assert result.exit_code == 0
    assert "TRAIDR Daily Run" in result.output
    assert "can_execute_trades: False" in result.output
    assert "What Was Scanned" in result.output
    assert "Top Opportunities" in result.output
    assert "Top Risks" in result.output
    with DuckDBStore(database, read_only=True) as store:
        tables = list_tables(store.connection)
        assert "research_reports" in tables
        assert "opportunity_radar_states" in tables
        report_count = store.execute(
            "SELECT COUNT(*) FROM research_reports WHERE report_type = 'daily_run'"
        ).fetchone()[0]
        radar_count = store.execute("SELECT COUNT(*) FROM opportunity_radar_states").fetchone()[0]
    assert report_count == 1
    assert radar_count > 0


def test_daily_run_can_disable_fixture_scan_without_execution(tmp_path: Path) -> None:
    database = tmp_path / "daily-run-no-fixture.duckdb"

    result = daily_run(str(database), fixture_scan=False)

    assert result.exit_code == 0
    assert "fixture_scan: False" in result.output
    assert "No Execution Actions" in result.output


def test_daily_run_deduplicates_rendered_candidates(tmp_path: Path) -> None:
    database = tmp_path / "daily-run-dedup.duckdb"

    first = daily_run(str(database))
    second = daily_run(str(database))

    assert first.exit_code == 0
    assert second.exit_code == 0
    opportunities = _section(second.output, "Top Opportunities")
    risks = _section(second.output, "Top Risks")
    assert opportunities.count("fixture-sol-usdc") == 1
    assert opportunities.count("fixture-bonk-usdc") == 1
    assert risks.count("fixture-sol-usdc") == 1
    assert risks.count("fixture-bonk-usdc") == 1


def test_main_dispatches_daily_run(tmp_path: Path, capsys) -> None:
    database = tmp_path / "daily-run-main.duckdb"

    exit_code = main(["daily-run", "--database", str(database)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "TRAIDR Daily Run" in output
    assert database.exists()


def _section(output: str, title: str) -> str:
    start = output.index(title)
    end = output.find("\n\n", start)
    return output[start:] if end == -1 else output[start:end]
