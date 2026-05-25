"""Read-only macro source contracts and fixture loader."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from intelligence.macro_regime import score_macro_regime

Transport = Callable[[], Mapping[str, Any] | None]
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"


@dataclass(frozen=True)
class MacroSourceResult:
    status: str
    signals: dict[str, float]
    score: dict[str, Any]
    reason_codes: tuple[str, ...]
    can_execute_trades: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "signals": dict(self.signals),
            "score": dict(self.score),
            "reason_codes": list(self.reason_codes),
            "can_execute_trades": self.can_execute_trades,
        }


def fixture_macro_result() -> MacroSourceResult:
    return build_macro_result({"fear_greed": 0.45, "btc_trend": 0.55, "stablecoin_liquidity": 0.5})


def default_fear_greed_transport() -> Mapping[str, Any] | None:
    request = Request(FEAR_GREED_URL, headers={"User-Agent": "TRAIDR-read-only-macro/0.1"}, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("macro source request failed") from exc


def fetch_macro_result(transport: Transport | None = None) -> MacroSourceResult:
    if transport is None:
        transport = default_fear_greed_transport
    try:
        payload = transport()
    except Exception:
        return MacroSourceResult("INSUFFICIENT_DATA", {}, {}, ("MACRO_SOURCE_FETCH_FAILED",))
    if payload is None:
        return MacroSourceResult("INSUFFICIENT_DATA", {}, {}, ("MACRO_SOURCE_MISSING",))
    signals = _signals_from_payload(payload)
    if not signals:
        return MacroSourceResult("INSUFFICIENT_DATA", {}, {}, ("MACRO_SOURCE_SIGNALS_MISSING",))
    return build_macro_result(signals)


def build_macro_result(signals: Mapping[str, float]) -> MacroSourceResult:
    score = score_macro_regime(signals)
    status = "OK" if score.classification != "INSUFFICIENT_DATA" else "INSUFFICIENT_DATA"
    return MacroSourceResult(status, dict(signals), score.to_dict(), ("MACRO_SOURCE_OK", *score.reason_codes))


def _signals_from_payload(payload: Mapping[str, Any]) -> dict[str, float]:
    if "signals" in payload and isinstance(payload["signals"], Mapping):
        return {str(key): _normalize(value) for key, value in payload["signals"].items() if _normalize(value) is not None}
    data = payload.get("data")
    if isinstance(data, list) and data:
        value = data[0].get("value") if isinstance(data[0], Mapping) else None
        normalized = _normalize_fear_greed(value)
        return {"fear_greed": normalized} if normalized is not None else {}
    normalized = _normalize_fear_greed(payload.get("value"))
    return {"fear_greed": normalized} if normalized is not None else {}


def _normalize(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0.0, min(1.0, float(value)))


def _normalize_fear_greed(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, number / 100.0))
