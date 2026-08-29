from functools import lru_cache

from database.racemanager import RaceManagerDatabase

from connector.config import get_settings
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_results_service import CurrentResultsService
from connector.services.event_service import EventService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_program_service import RaceProgramService
from connector.services.race_program_export_service import RaceProgramExportService
from connector.services.results_roll_service import ResultsRollService
from connector.services.sql_setup_service import PlanCache
from connector.services.sqorz_class_alias_service import SqorzClassAliasStore
from connector.services.sqorz_service import SqorzService


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
    return MotoboardService(
        get_database(),
        phase_override_file=get_settings().phase_override_file,
    )


@lru_cache
def get_current_moto_service() -> CurrentMotoService:
    settings = get_settings()
    return CurrentMotoService(
        settings.current_moto_state_file,
        default_moto=settings.current_moto_default,
    )


def get_race_program_service() -> RaceProgramService:
    return RaceProgramService(
        get_current_moto_service(),
        get_event_service(),
        get_motoboard_service(),
    )


def get_race_program_export_service() -> RaceProgramExportService:
    return RaceProgramExportService(
        get_database(),
        get_event_service(),
        get_motoboard_service(),
    )


@lru_cache
def get_sqorz_service() -> SqorzService:
    settings = get_settings()
    return SqorzService(
        enabled=settings.sqorz_enabled,
        mode=settings.sqorz_mode,
        event_id=settings.sqorz_event_id,
        org_code=settings.sqorz_org_code,
        host=settings.sqorz_host,
        port=settings.sqorz_port,
        file_path=settings.sqorz_file_path,
        poll_seconds=settings.sqorz_effective_poll_seconds,
        timeout_seconds=settings.sqorz_timeout_seconds,
        raw_response_file=settings.sqorz_lan_raw_response_file,
    )


@lru_cache
def get_sqorz_class_alias_store() -> SqorzClassAliasStore:
    return SqorzClassAliasStore(get_settings().sqorz_class_alias_file)


@lru_cache
def get_sql_wizard_plan_cache() -> PlanCache:
    return PlanCache()


def get_current_lineup_service() -> CurrentLineupService:
    settings = get_settings()
    return CurrentLineupService(
        get_current_moto_service(),
        get_event_service(),
        get_motoboard_service(),
        settings.lineup_cache_file,
        sqorz=get_sqorz_service(),
        sqorz_class_aliases=get_sqorz_class_alias_store(),
    )


@lru_cache
def get_current_results_service() -> CurrentResultsService:
    settings = get_settings()
    return CurrentResultsService(
        get_current_moto_service(),
        get_event_service(),
        get_motoboard_service(),
        get_current_lineup_service(),
        settings.results_cache_file,
    )


@lru_cache
def get_results_roll_service() -> ResultsRollService:
    settings = get_settings()
    return ResultsRollService(
        get_current_moto_service(),
        get_event_service(),
        get_current_results_service(),
        settings.results_roll_state_file,
    )
