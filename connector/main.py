"""FastAPI entry point for the BMX Broadcast Suite Connector."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database.racemanager import RaceManagerDatabaseError

from connector.config import get_settings
from connector.routes import event, health, motos

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Read-only JSON API for USABMX RaceManager broadcast data.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(event.router, prefix=settings.api_prefix)
app.include_router(motos.router, prefix=settings.api_prefix)


@app.exception_handler(RaceManagerDatabaseError)
def database_error_handler(
    request: Request, exc: RaceManagerDatabaseError
) -> JSONResponse:
    logging.getLogger(__name__).error("RaceManager database error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "RaceManager database is unavailable."},
    )
