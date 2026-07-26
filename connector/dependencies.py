from functools import lru_cache

from database.racemanager import RaceManagerDatabase

from connector.config import get_settings
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_lineup_service import CurrentLineupService


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


@lru_cache
def get_current_moto_service() -> CurrentMotoService:
    settings = get_settings()
    return CurrentMotoService(
        settings.current_moto_state_file,
        default_moto=settings.current_moto_default,
    )


def get_current_lineup_service() -> CurrentLineupService:
    return CurrentLineupService(
        get_current_moto_service(),
        get_event_service(),
        get_motoboard_service(),
    )

from connector.services.current_results_service import CurrentResultsService


def get_current_results_service() -> CurrentResultsService:
    return CurrentResultsService(
        get_current_moto_service(),
        get_event_service(),
        get_motoboard_service(),
        get_current_lineup_service(),
    )
