from functools import lru_cache

from database.racemanager import RaceManagerDatabase

from connector.config import get_settings
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService


@lru_cache
def get_database() -> RaceManagerDatabase:
    settings = get_settings()
    return RaceManagerDatabase(
        settings.connection_string,
        connect_timeout=settings.sql_connect_timeout,
        query_timeout=settings.sql_query_timeout,
    )


def get_event_service() -> EventService:
    return EventService(get_database())


def get_motoboard_service() -> MotoboardService:
    return MotoboardService(get_database())
