"""FastAPI entry point for the BMX Broadcast Suite Connector."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from database.racemanager import RaceManagerDatabaseError

from connector.config import get_settings
from connector.dependencies import get_results_roll_service
from connector.security import evaluate_http_access
from connector.routes import breaks, broadcast_ws, configuration, current, diagnostics, director, event, health, lineup, logs, manual, motos, results, setup, sqorz_match_report, sqorz_status, sqorz_timing, status as status_route, themes
from connector.services.logging_service import configure_logging

settings = get_settings()
configure_logging(settings.log_level, settings.log_dir, settings.log_retention_days)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_results_roll_service().start_worker()
    logger.info("BBS %s starting for %s on %s:%s", settings.app_version, settings.track_name, settings.app_host, settings.app_port)
    yield
    get_results_roll_service().shutdown()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Read-only JSON API for USABMX RaceManager broadcast data.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-BBS-Control-Token",
        "X-BBS-Admin-Token",
    ],
)

app.include_router(health.router)
app.include_router(status_route.router, prefix=settings.api_prefix)
app.include_router(event.router, prefix=settings.api_prefix)
app.include_router(motos.router, prefix=settings.api_prefix)
app.include_router(current.router, prefix=settings.api_prefix)
app.include_router(lineup.router, prefix=settings.api_prefix)
app.include_router(themes.router, prefix=settings.api_prefix)
app.include_router(diagnostics.router, prefix=settings.api_prefix)
app.include_router(results.router, prefix=settings.api_prefix)
app.include_router(breaks.router, prefix=settings.api_prefix)
app.include_router(configuration.router, prefix=settings.api_prefix)
app.include_router(logs.router, prefix=settings.api_prefix)
app.include_router(sqorz_timing.router, prefix=settings.api_prefix)
app.include_router(sqorz_match_report.router, prefix=settings.api_prefix)
app.include_router(sqorz_status.router, prefix=settings.api_prefix)
app.include_router(setup.router, prefix=settings.api_prefix)
app.include_router(manual.api_router, prefix=settings.api_prefix)
app.include_router(manual.router)
app.include_router(broadcast_ws.router)

# Human-facing pages live outside /api.
app.add_api_route("/logs", logs.logs_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/configuration", configuration.configuration_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/themes", themes.themes_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/diagnostics", diagnostics.diagnostics_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/director", director.race_director_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/controller", current.controller_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/overlay/current", current.current_moto_overlay, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/overlay/lineup", lineup.rider_lineup_overlay, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/overlay/results", results.results_overlay, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/overlay/break", breaks.break_overlay, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/overlay/sqorz-timing", sqorz_timing.sqorz_timing_overlay, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/sqorz-match-report", sqorz_match_report.sqorz_match_report_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/sqorz-status", sqorz_status.sqorz_status_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)
app.add_api_route("/setup", setup.setup_page, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)


@app.middleware("http")
async def access_control(request: Request, call_next):
    decision = evaluate_http_access(
        settings,
        method=request.method,
        path=request.url.path,
        client_host=request.client.host if request.client else None,
        headers=request.headers,
    )
    if not decision.allowed:
        return JSONResponse(
            status_code=decision.status_code,
            content={"detail": decision.detail},
        )
    return await call_next(request)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error: %s %s", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not request.url.path.startswith("/api/logs"):
        logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.exception_handler(RaceManagerDatabaseError)
def database_error_handler(
    request: Request, exc: RaceManagerDatabaseError
) -> JSONResponse:
    logging.getLogger(__name__).error("RaceManager database error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "RaceManager database is unavailable."},
    )
