from pathlib import Path


def test_intelligence_packages_do_not_import_execution_modules() -> None:
    root = Path(__file__).resolve().parents[2]
    scanned = []
    for package in ("intelligence", "radar", "notifications", "scheduler"):
        scanned.extend((root / package).glob("*.py"))

    contents = "\n".join(path.read_text(encoding="utf-8").lower() for path in scanned)

    assert "simulationbroker" not in contents
    assert "execution.simulation_broker" not in contents
    assert "record_order" not in contents
    assert "withdraw" not in contents
