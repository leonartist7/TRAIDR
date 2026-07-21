"""Browser-level cockpit checks; all market rendering stays local and read-only."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest


playwright = pytest.importorskip("playwright.sync_api")


def test_streamlit_cockpit_interactions_and_health_controls(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(root / "dashboard" / "app.py"),
            "--server.headless=true",
            f"--server.port={port}",
            "--server.address=127.0.0.1",
            "--browser.gatherUsageStats=false",
        ],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_ready(port, process)
        with playwright.sync_playwright() as runtime:
            try:
                browser = runtime.chromium.launch(headless=True)
            except Exception as exc:  # local machines may not have Playwright browsers yet
                pytest.skip(f"Playwright Chromium unavailable: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
            page.get_by_label("DuckDB path").fill(str(tmp_path / "missing.duckdb"))
            page.get_by_label("Data mode").click()
            page.get_by_role("option", name="preview", exact=True).click()
            page.get_by_label("Interval").click()
            page.get_by_role("option", name="15m", exact=True).click()
            page.get_by_text("PREVIEW MODE", exact=False).wait_for()
            iframe = page.locator("iframe").first
            iframe.wait_for()
            canvas = iframe.content_frame.locator("canvas")
            canvas.wait_for()
            box = canvas.bounding_box()
            assert box is not None
            canvas.hover(position={"x": 400, "y": 250})
            page.mouse.wheel(0, -400)
            page.mouse.move(box["x"] + 700, box["y"] + 300)
            page.mouse.down()
            page.mouse.move(box["x"] + 500, box["y"] + 300)
            page.mouse.up()
            page.get_by_role("tab", name="System Health").click()
            page.get_by_text("Service", exact=True).wait_for()
            assert page.get_by_text("OFFLINE", exact=True).is_visible()
            assert page.get_by_role("button", name="Refresh Research Service").is_visible()
            assert page.get_by_role("button", name="Enable Auto Paper Simulation").is_visible()
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(port: int, process: subprocess.Popen[bytes]) -> None:
    for _ in range(80):
        if process.poll() is not None:
            raise RuntimeError("Streamlit stopped before browser tests connected")
        try:
            with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Streamlit did not become ready")
