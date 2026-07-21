"""Loopback-only allowlisted controls for the local research service."""

from __future__ import annotations

import json
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

ControlCallback = Callable[[str, dict[str, Any]], dict[str, Any]]
ALLOWED_ACTIONS = frozenset({"refresh", "paper_enable", "paper_disable"})


class LocalControlServer:
    def __init__(self, host: str, port: int, callback: ControlCallback) -> None:
        if host != "127.0.0.1":
            raise ValueError("TRAIDR control server must bind to 127.0.0.1")
        self.host = host
        self.port = port
        self.callback = callback
        handler = self._handler_type()
        self.server = ThreadingHTTPServer((host, port), handler)
        self.thread = Thread(target=self.server.serve_forever, name="traidr-control-api", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _handler_type(self) -> type[BaseHTTPRequestHandler]:
        callback = self.callback

        class Handler(BaseHTTPRequestHandler):
            server_version = "TRAIDRLocalControl/1"

            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/health":
                    self._respond(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND"})
                    return
                self._respond(
                    HTTPStatus.OK,
                    {"status": "OK", "local_only": True, "can_execute_trades": False},
                )

            def do_POST(self) -> None:  # noqa: N802
                if self.headers.get("X-TRAIDR-Control") != "local-dashboard":
                    self._respond(HTTPStatus.FORBIDDEN, {"status": "REJECTED"})
                    return
                action = self.path.removeprefix("/")
                if action not in ALLOWED_ACTIONS:
                    self._respond(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 4096:
                        raise ValueError("control payload too large")
                    payload = json.loads(self.rfile.read(length) or b"{}")
                    if not isinstance(payload, dict):
                        raise ValueError("control payload must be an object")
                    result = callback(action, payload)
                except (ValueError, json.JSONDecodeError):
                    self._respond(HTTPStatus.BAD_REQUEST, {"status": "REJECTED"})
                    return
                self._respond(HTTPStatus.ACCEPTED, result)

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _respond(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

        return Handler
