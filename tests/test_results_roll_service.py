from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from connector.models import (
    ActiveGraphic,
    CurrentMotoUpdate,
    CurrentResults,
    Event,
    RacePhase,
    ResultRider,
    ResultsRollStart,
)
from connector.services.current_moto_service import CurrentMotoService
from connector.services.results_roll_service import (
    ResultsRollService,
    ResultsRollUnavailableError,
)


BOARD_ID = UUID("d726697c-36e3-4a4c-b21b-c65058dc31bf")


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2025, 5, 31, 20, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class HistoricEvents:
    def __init__(self) -> None:
        self.by_board_calls = 0
        self.current_calls = 0

    def by_motoboard(self, board_id):
        self.by_board_calls += 1
        assert board_id == BOARD_ID
        return Event(
            event_id=UUID("10000000-0000-0000-0000-000000000001"),
            event_name="State Qualifier",
            date_begin="2025-05-31",
            race_id=UUID("20000000-0000-0000-0000-000000000002"),
            race_description="State Qualifier",
            motoboard_id=BOARD_ID,
            total_motos=56,
            total_riders=253,
        )

    def current(self):
        self.current_calls += 1
        raise AssertionError("Pinned historic events must not switch to the latest event")


def result(
    moto_number: int,
    index: int,
    total: int,
    *,
    phase: RacePhase = RacePhase.MAIN,
) -> CurrentResults:
    return CurrentResults(
        event_name="State Qualifier",
        moto_number=moto_number,
        race_phase=phase,
        phase_label="Round 1" if phase == RacePhase.ROUND_1 else "Main",
        motoboard_id=BOARD_ID,
        class_name=f"Class {moto_number}",
        riders=[
            ResultRider(
                finish=1,
                bike_number=moto_number,
                first_name="Rider",
                last_name=str(moto_number),
            )
        ],
        source="racemanager",
        progress_index=index,
        progress_total=total,
    )


class Results:
    def __init__(self) -> None:
        self.items = [
            result(23, 1, 4),
            result(25, 2, 4),
            result(27, 3, 4),
            result(29, 4, 4),
        ]
        self.catalog_calls = 0

    def catalog(self, board_id, *, event_name=None):
        self.catalog_calls += 1
        assert board_id == BOARD_ID
        assert event_name == "State Qualifier"
        return [item.model_copy(deep=True) for item in self.items]

    def get(self):
        return self.items[1].model_copy(deep=True)


def service(tmp_path: Path):
    clock = Clock()
    events = HistoricEvents()
    results = Results()
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(
        CurrentMotoUpdate(
            moto_number=25,
            race_phase=RacePhase.MAIN,
            motoboard_id=BOARD_ID,
            class_name="5 & Under Intermediate",
        )
    )
    roll = ResultsRollService(
        current,
        events,
        results,
        tmp_path / "results-roll.json",
        clock=clock,
    )
    return roll, current, events, results, clock


def race_position(current: CurrentMotoService):
    state = current.get()
    return state.moto_number, state.race_phase, state.motoboard_id, state.class_name


def test_start_from_first_uses_pinned_event_without_mutating_race_position(tmp_path: Path) -> None:
    roll, current, events, _results, _clock = service(tmp_path)
    before = race_position(current)

    state = roll.start(ResultsRollStart(start_from="first", interval_seconds=10))

    assert state.active is True
    assert state.paused is False
    assert state.current_result_moto == 23
    assert state.total_available_results == 4
    assert roll.current_result().race_phase == RacePhase.MAIN
    assert current.get().active_graphic == ActiveGraphic.RESULTS
    assert race_position(current) == before
    assert events.by_board_calls == 1
    assert events.current_calls == 0
    roll.shutdown()


def test_start_from_current_automatic_progress_pause_resume_and_manual_steps(tmp_path: Path) -> None:
    roll, current, _events, results, clock = service(tmp_path)
    before = race_position(current)
    state = roll.start(ResultsRollStart(start_from="current", interval_seconds=10))
    assert state.current_result_moto == 25
    assert roll.current_result().race_phase == RacePhase.MAIN

    clock.advance(9)
    assert roll.tick().current_result_moto == 25
    clock.advance(1)
    assert roll.tick().current_result_moto == 27
    assert results.catalog_calls == 1

    paused = roll.pause()
    assert paused.paused is True
    assert paused.next_change_at is None
    assert roll.previous().current_result_moto == 25
    assert roll.next().current_result_moto == 27
    clock.advance(30)
    assert roll.tick().current_result_moto == 27

    resumed = roll.resume()
    assert resumed.paused is False
    clock.advance(10)
    ended = roll.tick()
    assert ended.current_result_moto == 29
    assert ended.active is False
    assert ended.next_change_at is None
    assert race_position(current) == before
    roll.shutdown()


def test_hide_all_pause_and_worker_are_idempotent(tmp_path: Path) -> None:
    roll, _current, _events, _results, _clock = service(tmp_path)
    roll.start(ResultsRollStart())
    roll.start_worker()
    worker = roll._worker
    roll.start_worker()
    assert roll._worker is worker
    assert roll.pause_if_active().paused is True
    assert roll.stop().active is False
    roll.shutdown()


def test_show_current_and_manual_navigation_keep_result_on_air(tmp_path: Path) -> None:
    roll, current, _events, _results, _clock = service(tmp_path)

    status = roll.show_current()

    assert status.active is False
    assert status.current_result_moto == 25
    assert roll.current_result().moto_number == 25
    assert current.get().active_graphic == ActiveGraphic.RESULTS
    roll.shutdown()


def test_show_current_rejects_non_main_phase_without_changing_graphic(tmp_path: Path) -> None:
    roll, current, _events, _results, _clock = service(tmp_path)
    current.set(
        CurrentMotoUpdate(
            moto_number=25,
            race_phase=RacePhase.ROUND_1,
            motoboard_id=BOARD_ID,
        )
    )
    before = current.get()

    try:
        roll.show_current()
    except ResultsRollUnavailableError as exc:
        assert "Select a Main" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Non-Main results should not be shown")

    assert current.get().active_graphic == before.active_graphic
    assert roll.status().total_available_results == 0
    roll.shutdown()
