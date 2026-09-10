"""Loopback-only, read-only FastAPI surface for the TRAIDR visual platform."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dashboard.queries import configured_database_path
from web_api.contracts import (
    ApiEnvelope,
    ApiStatus,
    ErrorData,
    MarketData,
    MarketsData,
    OverviewData,
    ScannerData,
    StatusData,
)
from web_api.read_models import (
    MAX_API_AGE_SECONDS,
    build_market,
    build_markets,
    build_overview,
    build_scanner,
    build_status,
    freshness_for,
    latest_observation,
    read_dashboard,
    reason_codes_for,
    scanner_reason_codes,
    status_for,
)

LOOPBACK_HOST = "127.0.0.1"
LOOPBACK_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ScannerStatus = Literal["OK", "DEGRADED", "NO_TRADE", "INSUFFICIENT_DATA"]
ScannerDirection = Literal["LONG", "SHORT", "NO_TRADE"]
MarketInterval = Literal["1m", "5m", "15m", "1h", "4h", "1d"]


class ReadModelError(RuntimeError):
    """Internal marker for a local read failure with a safe public response."""


def create_app(database_path: str | Path | None = None) -> FastAPI:
    """Create a local read-only API app without starting a listener."""

    app = FastAPI(
        title="TRAIDR Local Research API",
        description="Read-only market research, scanner, chart, and paper-state views.",
        version="0.2.0",
    )
    app.state.database_path = Path(database_path) if database_path is not None else None
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOOPBACK_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        request_id = _request_id(request)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, _: RequestValidationError) -> JSONResponse:
        return _error_response(request, 422, "REQUEST_VALIDATION", "Request parameters are invalid.")

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, _: ValueError) -> JSONResponse:
        return _error_response(request, 400, "INVALID_REQUEST", "The request could not be satisfied.")

    @app.exception_handler(Exception)
    async def read_error_handler(request: Request, _: Exception) -> JSONResponse:
        return _error_response(request, 500, "READ_MODEL_ERROR", "Local research data could not be read safely.")

    @app.exception_handler(ReadModelError)
    async def read_model_error_handler(request: Request, _: ReadModelError) -> JSONResponse:
        return _error_response(request, 500, "READ_MODEL_ERROR", "Local research data could not be read safely.")

    @app.get("/health", response_model=ApiEnvelope[StatusData], tags=["status"])
    @app.get("/api/v1/status", response_model=ApiEnvelope[StatusData], tags=["status"])
    def status(request: Request) -> ApiEnvelope[StatusData]:
        data = _read(app, limit=20)
        status_data = build_status(data)
        has_data = bool(data.service_heartbeats or data.data_health or data.scanner_scores)
        return _envelope(
            request,
            status=status_for(data, has_data=has_data),
            data=status_data,
            freshness=_freshness(latest_observation(data)),
            reason_codes=reason_codes_for(data, has_data=has_data),
        )

    @app.get("/api/v1/overview", response_model=ApiEnvelope[OverviewData], tags=["overview"])
    def overview(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 20,
    ) -> ApiEnvelope[OverviewData]:
        data = _read(app, limit=limit)
        overview_data = build_overview(data, limit=limit)
        has_data = bool(
            overview_data.scanner
            or overview_data.alerts
            or overview_data.paper_positions
            or overview_data.service_heartbeats
        )
        return _envelope(
            request,
            status=status_for(data, has_data=has_data),
            data=overview_data,
            freshness=_freshness(latest_observation(data)),
            reason_codes=reason_codes_for(data, has_data=has_data),
        )

    @app.get("/api/v1/scanner", response_model=ApiEnvelope[ScannerData], tags=["scanner"])
    def scanner(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 20,
        status_filter: Annotated[ScannerStatus | None, Query(alias="status")] = None,
        direction: ScannerDirection | None = None,
    ) -> ApiEnvelope[ScannerData]:
        data = _read(app, limit=limit)
        scanner_data = build_scanner(
            data,
            limit=limit,
            status=status_filter,
            direction=direction,
        )
        has_data = bool(scanner_data.rows)
        return _envelope(
            request,
            status=status_for(data, has_data=has_data),
            data=scanner_data,
            freshness=_freshness(
                max((row.observed_at for row in scanner_data.rows if row.observed_at is not None), default=None)
            ),
            reason_codes=scanner_reason_codes(data, has_data=has_data),
        )

    @app.get(
        "/api/v1/scanner/{instrument_id}",
        response_model=ApiEnvelope[ScannerData],
        tags=["scanner"],
    )
    def scanner_detail(
        request: Request,
        instrument_id: str,
        limit: Annotated[int, Query(ge=1, le=20)] = 1,
    ) -> ApiEnvelope[ScannerData]:
        data = _read(app, limit=200)
        scanner_data = build_scanner(data, limit=limit, instrument_id=instrument_id)
        has_data = bool(scanner_data.rows)
        return _envelope(
            request,
            status=status_for(data, has_data=has_data),
            data=scanner_data,
            freshness=_freshness(
                max((row.observed_at for row in scanner_data.rows if row.observed_at is not None), default=None)
            ),
            reason_codes=scanner_reason_codes(data, has_data=has_data),
        )

    @app.get(
        "/api/v1/markets",
        response_model=ApiEnvelope[MarketsData],
        tags=["markets"],
    )
    def markets(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 200,
    ) -> ApiEnvelope[MarketsData]:
        data = _read(app, limit=limit)
        markets_data = build_markets(data, limit=limit)
        has_data = bool(markets_data.instruments)
        return _envelope(
            request,
            status=status_for(data, has_data=has_data),
            data=markets_data,
            freshness=_freshness(
                max(
                    (instrument.refreshed_at for instrument in markets_data.instruments),
                    default=None,
                )
            ),
            reason_codes=reason_codes_for(data, has_data=has_data),
        )

    @app.get(
        "/api/v1/markets/{instrument_id}",
        response_model=ApiEnvelope[MarketData],
        tags=["markets"],
    )
    @app.get(
        "/api/v1/markets/{instrument_id}/chart",
        response_model=ApiEnvelope[MarketData],
        tags=["markets"],
    )
    def market(
        request: Request,
        instrument_id: str,
        interval: Annotated[MarketInterval, Query()] = "1h",
        limit: Annotated[int, Query(ge=1, le=2_000)] = 200,
    ) -> ApiEnvelope[MarketData]:
        data = _read(app, limit=limit)
        market_data = build_market(
            data,
            instrument_id=instrument_id,
            interval=interval,
            limit=limit,
        )
        has_data = bool(
            market_data.candles
            or market_data.scanner
            or market_data.microstructure
            or market_data.evidence
        )
        observed_at = max(
            (
                datetime.fromtimestamp(candle.open_time_ms / 1000, tz=UTC)
                for candle in market_data.candles
            ),
            default=None,
        )
        return _envelope(
            request,
            status=status_for(data, has_data=has_data),
            data=market_data,
            freshness=_freshness(observed_at),
            reason_codes=reason_codes_for(data, has_data=has_data),
        )

    return app


def run_api(
    database_path: str | Path | None = None,
    *,
    host: str = LOOPBACK_HOST,
    port: int = 8787,
) -> None:
    """Run the API on loopback only; remote binding is intentionally rejected."""

    validate_loopback_host(host)
    if not 1 <= port <= 65_535:
        raise ValueError("port must be between 1 and 65535")
    import uvicorn

    uvicorn.run(create_app(database_path), host=host, port=port, access_log=False)


def validate_loopback_host(host: str) -> None:
    if host != LOOPBACK_HOST:
        raise ValueError("TRAIDR API must bind to 127.0.0.1")


def _read(app: FastAPI, *, limit: int) -> Any:
    database_path = app.state.database_path
    try:
        return read_dashboard(database_path or configured_database_path(), limit=limit)
    except Exception as exc:
        raise ReadModelError from exc


def _request_id(request: Request) -> str:
    candidate = request.headers.get("X-Request-ID", "")
    return candidate if _REQUEST_ID.fullmatch(candidate) else f"read-{uuid4().hex}"


def _freshness(observed_at: datetime | None) -> dict[str, Any]:
    if observed_at is None:
        return {"data": freshness_for(None, maximum_age_seconds=MAX_API_AGE_SECONDS)}
    return {"data": freshness_for(observed_at, maximum_age_seconds=MAX_API_AGE_SECONDS)}


def _envelope(
    request: Request,
    *,
    status: ApiStatus,
    data: Any,
    freshness: dict[str, Any],
    reason_codes: tuple[str, ...],
) -> ApiEnvelope[Any]:
    return ApiEnvelope(
        status=status,
        as_of=datetime.now(tz=UTC),
        data=data,
        freshness=freshness,
        reason_codes=reason_codes,
        request_id=getattr(request.state, "request_id", f"read-{uuid4().hex}"),
    )


def _error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    envelope = _envelope(
        request,
        status="ERROR",
        data=ErrorData(code=code, message=message),
        freshness={},
        reason_codes=(code,),
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))
