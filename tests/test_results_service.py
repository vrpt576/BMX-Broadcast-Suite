from pathlib import Path
from uuid import UUID

from connector.models import (
    CurrentMotoUpdate,
    MotoList,
    RacePhase,
    ResultsRollStart,
)
from connector.services.current_lineup_service import CurrentLineupService, DEMO_MOTO
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_results_service import CurrentResultsService
from connector.services.round_label_service import RoundLabelResolver


class Noop:
    pass


class _NoRoundsDatabase:
    def fetch_all(self, query, params=None):
        return []


def test_demo_results_are_sorted_by_finish(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(CurrentMotoUpdate(moto_number=1))
    lineups = CurrentLineupService(current, Noop(), Noop(), tmp_path / "cache.json")
    service = CurrentResultsService(current, Noop(), Noop(), lineups)
    result = service.get(demo=True)
    assert [rider.finish for rider in result.riders] == [1, 2, 3, 4]
    assert result.race_phase == RacePhase.MAIN
    assert result.result_status == "official"
    assert result.event_name == "DEMO DATA - BBS Showcase"
    assert { (rider.bike_number, rider.age, rider.home_track) for rider in result.riders } == {
        (rider.bike_number, rider.age, rider.home_track)
        for rider in lineups.get(demo=True).riders
    }


def _moto(
    number: int,
    *,
    class_number: int,
    round_type_id: int,
    finishes: list[int | str | None],
):
    class_id = UUID(f"10000000-0000-0000-0000-{class_number:012d}")
    group_id = UUID(f"20000000-0000-0000-0000-{number * 10 + round_type_id:012d}")
    round_id = UUID(f"30000000-0000-0000-0000-{number * 10 + round_type_id:012d}")
    moto = DEMO_MOTO.model_copy(
        deep=True,
        update={
            "moto_number": number,
            "motogroup_id": group_id,
            "round_id": round_id,
            "class_id": class_id,
            "class_name": f"Class {number}",
            "round_type_id": round_type_id,
        },
    )
    moto.riders = moto.riders[: len(finishes)]
    for position, (rider, finish) in enumerate(zip(moto.riders, finishes), 1):
        rider.rider_id = UUID(f"40000000-0000-0000-0000-{class_number * 100 + position:012d}")
        rider.finish_1 = finish
    return moto


class CatalogMotos:
    def __init__(self) -> None:
        qualifier_main = _moto(
            1,
            class_number=1,
            round_type_id=123,
            finishes=["X", 2, 3, 4],
        )
        for rider, finish in zip(qualifier_main.riders, (4, 3, 2, 1)):
            rider.finish_2 = finish
        final_main = _moto(
            1,
            class_number=1,
            round_type_id=1,
            finishes=[3, 1, 4, 2],
        )
        qualifier_missing = _moto(
            2,
            class_number=2,
            round_type_id=123,
            finishes=[1, 2, 3],
        )
        final_missing = _moto(
            2,
            class_number=2,
            round_type_id=1,
            finishes=[None, None, None],
        )
        qualifier_partial = _moto(
            3,
            class_number=3,
            round_type_id=123,
            finishes=["X", 2, 3],
        )
        final_partial = _moto(
            3,
            class_number=3,
            round_type_id=1,
            finishes=[1, None, 2],
        )
        qualifier_same_riders = _moto(
            4,
            class_number=4,
            round_type_id=123,
            finishes=[1, 2, 3],
        )
        final_same_riders = _moto(
            4,
            class_number=4,
            round_type_id=1,
            finishes=[2, 3, 1],
        )
        self.motos = [
            qualifier_main,
            final_main,
            qualifier_missing,
            final_missing,
            qualifier_partial,
            final_partial,
            qualifier_same_riders,
            final_same_riders,
        ]
        self.calls = 0
        self.round_labels = RoundLabelResolver(_NoRoundsDatabase())

    def list_motos(self, board_id, *, round_type_id=None):
        self.calls += 1
        return MotoList(motoboard_id=board_id, count=len(self.motos), motos=self.motos)


def test_official_catalog_orders_finishes_and_skips_missing_results(tmp_path: Path) -> None:
    board_id = UUID("50000000-0000-0000-0000-000000000001")
    current = CurrentMotoService(tmp_path / "current.json")
    motos = CatalogMotos()
    service = CurrentResultsService(
        current,
        Noop(),
        motos,
        Noop(),
        tmp_path / "results-cache.json",
    )

    catalog = service.catalog(board_id, event_name="2025 State Qualifier")

    assert [(result.race_phase, result.moto_number) for result in catalog] == [
        (RacePhase.MAIN, 1),
        (RacePhase.MAIN, 3),
        (RacePhase.MAIN, 4),
    ]
    main = next(
        result
        for result in catalog
        if result.race_phase == RacePhase.MAIN and result.moto_number == 1
    )
    partial = next(
        result
        for result in catalog
        if result.race_phase == RacePhase.MAIN and result.moto_number == 3
    )
    assert [rider.finish for rider in main.riders] == [1, 2, 3, 4]
    assert main.result_status == "official"
    assert partial.result_status == "incomplete"
    assert next(rider for rider in partial.riders if rider.finish is None).status is None
    direct_main = next(result for result in catalog if result.moto_number == 4)
    assert [rider.finish for rider in direct_main.riders] == [1, 2, 3]
    assert [result.progress_index for result in catalog] == [1, 2, 3]
    assert all(result.progress_total == 3 for result in catalog)
    assert all(result.event_name == "2025 State Qualifier" for result in catalog)
    assert all(result.race_phase == RacePhase.MAIN for result in catalog)
    assert not any(result.moto_number == 2 for result in catalog)

    # The completed catalog is reused without another RaceManager query.
    assert service.catalog(board_id) == catalog
    assert motos.calls == 1


def test_results_start_interval_is_validated() -> None:
    assert ResultsRollStart().interval_seconds == 10
    for invalid in (1, 301):
        try:
            ResultsRollStart(interval_seconds=invalid)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"Interval {invalid} should be rejected")


def test_cached_current_result_survives_database_failure(tmp_path: Path) -> None:
    current = CurrentMotoService(tmp_path / "current.json")
    lineups = CurrentLineupService(current, Noop(), Noop(), tmp_path / "lineup.json")
    service = CurrentResultsService(
        current,
        Noop(),
        Noop(),
        lineups,
        tmp_path / "results.json",
    )
    cached = service.get(demo=True)
    cached = cached.model_copy(
        update={
            "motoboard_id": UUID("60000000-0000-0000-0000-000000000001"),
            "source": "racemanager",
        }
    )
    service._write_cache(cached)

    result = service.get(motoboard_id=cached.motoboard_id)

    assert result.source == "cache"
    assert result.is_stale is True
    assert result.riders == cached.riders
