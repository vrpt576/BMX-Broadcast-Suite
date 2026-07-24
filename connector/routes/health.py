from fastapi import APIRouter, Depends

from database.racemanager import RaceManagerDatabase, RaceManagerDatabaseError

from connector.config import Settings, get_settings
from connector.dependencies import get_database
from connector.models import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    database: RaceManagerDatabase = Depends(get_database),
) -> HealthResponse:
    database_status = "connected"
    status = "ok"
    try:
        database.fetch_one("SELECT 1 AS ok")
    except RaceManagerDatabaseError:
        database_status = "unavailable"
        status = "degraded"
    return HealthResponse(
        status=status,
        version=settings.app_version,
        database=database_status,
    )
