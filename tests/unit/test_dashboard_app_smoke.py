from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_read_only_cockpit_and_health_controls() -> None:
    app_path = Path(__file__).resolve().parents[2] / "dashboard" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()

    assert not app.exception
    assert any(tab.label == "Cockpit" for tab in app.tabs)
    assert any(tab.label == "System Health" for tab in app.tabs)
    labels = {button.label for button in app.button}
    assert "Refresh Real Bitunix Data" in labels
    assert "Refresh Research Service" in labels
    assert "Run Daily Workflow" not in labels
    assert "Run Paper Simulation" not in labels
