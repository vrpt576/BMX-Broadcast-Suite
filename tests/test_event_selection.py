from pathlib import Path
from uuid import UUID

from connector.config import Settings
from connector.models import CurrentMotoUpdate
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_results_service import CurrentResultsService
from connector.services.event_service import EventService
from database import queries


BOARD_ONE = UUID("10000000-0000-0000-0000-000000000001")
BOARD_TWO = UUID("20000000-0000-0000-0000-000000000002")
EVENT_ID = UUID("30000000-0000-0000-0000-000000000003")
RACE_ID = UUID("40000000-0000-0000-0000-000000000004")


class EventDatabase:
    def __init__(self) -> None:
        self.query = None

    def fetch_all(self, query, params=None):
        self.query = query
        assert params is None
        return [
            {
                "event_id": EVENT_ID,
                "event_name": "Historic National",
                "location": "Test Track",
                "date_begin": "2026-07-01",
                "date_end": "2026-07-03",
                "race_id": RACE_ID,
                "race_description": "Day 2",
                "motoboard_id": BOARD_ONE,
                "total_motos": 120,
                "total_riders": 640,
                "updated_at": "2026-07-03T22:00:00",
            }
        ]


class CurrentEventMustNotBeUsed:
    def current(self):  # pragma: no cover - failure path only
        raise AssertionError("Historic selection should not resolve the latest event")


class RecordingMotos:
    def __init__(self) -> None:
        self.board_id = None
        self.moto_number = None

    def get_moto(self, board_id, moto_number):
        self.board_id = board_id
        self.moto_number = moto_number
        return DEMO_MOTO.model_copy(deep=True)


class UnusedLineups:
    def get(self, **_kwargs):  # pragma: no cover - failure path only
        raise AssertionError("Results fallback should not be used")


def current_service(tmp_path: Path) -> CurrentMotoService:
    return CurrentMotoService(tmp_path / "current.json")


def test_event_service_lists_motoboards() -> None:
    database = EventDatabase()
    events = EventService(database).list_events()

    assert database.query == queries.EVENTS
    assert len(events) == 1
    assert events[0].motoboard_id == BOARD_ONE
    assert events[0].race_description == "Day 2"


def test_timeout_defaults_fail_faster_offline() -> None:
    settings = Settings(_env_file=None)
    assert settings.sql_connect_timeout == 2
    assert settings.sql_query_timeout == 5


def test_historic_selection_persists_and_moto_steps_preserve_it(tmp_path: Path) -> None:
    current = current_service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=1, motoboard_id=BOARD_ONE))

    assert current.next().motoboard_id == BOARD_ONE
    assert current.previous().motoboard_id == BOARD_ONE
    assert current_service(tmp_path).get().motoboard_id == BOARD_ONE


def test_explicit_null_returns_to_latest_live(tmp_path: Path) -> None:
    current = current_service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=1, motoboard_id=BOARD_ONE))

    state = current.set(CurrentMotoUpdate(moto_number=1, motoboard_id=None))

    assert state.motoboard_id is None
    assert current_service(tmp_path).get().motoboard_id is None


def test_historic_lineup_uses_selected_motoboard(tmp_path: Path) -> None:
    current = current_service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=1, motoboard_id=BOARD_ONE))
    motos = RecordingMotos()
    service = CurrentLineupService(
        current,
        CurrentEventMustNotBeUsed(),
        motos,
        tmp_path / "lineup-cache.json",
    )

    lineup = service.get()

    assert motos.board_id == BOARD_ONE
    assert lineup.motoboard_id == BOARD_ONE
    assert lineup.source == "racemanager"


def test_historic_results_use_selected_motoboard(tmp_path: Path) -> None:
    current = current_service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=1, motoboard_id=BOARD_TWO))
    motos = RecordingMotos()
    service = CurrentResultsService(
        current,
        CurrentEventMustNotBeUsed(),
        motos,
        UnusedLineups(),
    )

    results = service.get()

    assert motos.board_id == BOARD_TWO
    assert results.motoboard_id == BOARD_TWO
    assert [rider.finish for rider in results.riders] == [1, 2, 3, 4]


def test_historic_cache_is_not_reused_for_another_event(tmp_path: Path) -> None:
    current = current_service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=1, motoboard_id=BOARD_ONE))
    cache_file = tmp_path / "lineup-cache.json"
    first = CurrentLineupService(
        current,
        CurrentEventMustNotBeUsed(),
        RecordingMotos(),
        cache_file,
    )
    first.get()

    current.set(CurrentMotoUpdate(moto_number=1, motoboard_id=BOARD_TWO))

    class OfflineMotos:
        def get_moto(self, *_args):
            raise RuntimeError("offline")

    second = CurrentLineupService(
        current,
        CurrentEventMustNotBeUsed(),
        OfflineMotos(),
        cache_file,
    )

    try:
        second.get()
    except RuntimeError as exc:
        assert str(exc) == "offline"
    else:  # pragma: no cover
        raise AssertionError("Cache from a different motoboard must not be reused")
