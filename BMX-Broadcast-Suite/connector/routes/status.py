"""Compact connector status endpoint for desktop integrations."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from connector.config import Settings, get_settings
from connector.dependencies import get_current_moto_service, get_database
from connector.services.current_moto_service import CurrentMotoService
from database.racemanager import RaceManagerDatabase, RaceManagerDatabaseError

router = APIRouter(tags=["system"])


@router.get("/status")
def connector_status(
    settings: Settings = Depends(get_settings),
    database: RaceManagerDatabase = Depends(get_database),
    current_service: CurrentMotoService = Depends(get_current_moto_service),
) -> dict[str, object]:
    """Return the small status payload consumed by the Linux tray icon."""
    database_status = "connected"
    try:
        database.fetch_one("SELECT 1 AS ok")
    except RaceManagerDatabaseError:
        database_status = "unavailable"

    current = current_service.get()
    return {
        "version": settings.app_version,
        "connector": "running",
        "database": database_status,
        "track_name": settings.track_name,
        "moto_number": current.moto_number,
        "race_phase": current.race_phase.value,
        "class_name": current.class_name,
    }
