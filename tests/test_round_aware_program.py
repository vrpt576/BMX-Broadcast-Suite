"""Regression tests for RaceManager's qualifier/final parallel branches."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from connector.models import CurrentMoto, RacePhase
from connector.services.current_results_service import CurrentResultsService
from connector.services.motoboard_service import (
    MotoboardService,
    RacePhaseUnavailableError,
)

BOARD_ID = UUID("d726697c-36e3-4a4c-b21b-c65058dc31bf")
CLASS_SPLIT = UUID("95379986-aef2-4427-b647-d282e14b3474")
ROUND_SPLIT_QUAL = UUID("bda21581-a096-4a95-be36-6f815b6cb26c")
ROUND_SPLIT_FINAL = UUID("e3bde226-ce52-4aed-a433-ebc2e35cd934")
GROUP_30 = UUID("dac55f25-30f3-41af-9815-36ba21aaca0f")
GROUP_31 = UUID("1214fe52-8214-4e59-8550-46a2e0fbd9e1")
GROUP_FINAL = UUID("040748b2-d4a0-472d-b818-4f61b55f511f")

CLASS_POINTS = UUID("73452dc6-6f33-438a-9423-9038c6d1cd69")
ROUND_POINTS_QUAL = UUID("8e046a40-f631-4275-8c57-9a3d0ce7d699")
ROUND_POINTS_FINAL = UUID("9797955e-49fc-41b9-9ddf-6824495b8a64")
GROUP_POINTS_QUAL = UUID("a08c767a-b4bd-491b-831a-79e97d85e09f")
GROUP_POINTS_FINAL = UUID("f1a7f07b-d2cd-42aa-a859-34d248b696b5")


def _rider_id(number: int) -> UUID:
    return UUID(f"00000000-0000-0000-0000-{number:012d}")


def row(
    *,
    class_id: UUID,
    class_name: str,
    round_id: UUID,
    round_type_id: int,
    motogroup_id: UUID,
    moto_number: int,
    rider_number: int,
    rider_order: int,
    lane_1: int,
    lane_2: int = 0,
    lane_3: int = 0,
    finish_1: int | str | None = None,
    finish_2: int | str | None = None,
    finish_3: int | str | None = None,
) -> dict[str, object]:
    return {
        "moto_number": moto_number,
        "motogroup_number": 1,
        "motogroup_id": motogroup_id,
        "class_id": class_id,
        "class_name": class_name,
        "class_name_short": class_name,
        "round_id": round_id,
        "round_type_id": round_type_id,
        "motogroup_rider_id": _rider_id(9000 + rider_number + round_type_id),
        "rider_order": rider_order,
        "lane_1": lane_1,
        "lane_2": lane_2,
        "lane_3": lane_3,
        "finish_1": finish_1,
        "finish_2": finish_2,
        "finish_3": finish_3,
        "did_not_race": False,
        "updated_at": datetime(2025, 7, 14, 17, 44, 22),
        "rider_id": _rider_id(rider_number),
        "bike_number": rider_number,
        "first_name": f"Rider{rider_number}",
        "last_name": "Test",
        "nickname": None,
        "proficiency": "I",
        "sponsor": None,
    }


class FakeDatabase:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def column_exists(self, *_args: object) -> bool:
        return False

    def fetch_all(self, query: str, params=None):
        params = list(params or [])
        rows = self.rows
        if "ro.Round_Type_ID = 123" in query:
            rows = [item for item in rows if item["round_type_id"] == 123]
        if "mg.Moto_Number = ?" in query:
            rows = [item for item in rows if item["moto_number"] == params[-1]]
        if "mg.Motogroup_DBID = ?" in query:
            rows = [item for item in rows if item["motogroup_id"] == params[-1]]
        if "ac.Age_Class_DBID = ?" in query:
            rows = [item for item in rows if item["class_id"] == params[-1]]
        return rows


def split_class_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    # Eleven riders split across two qualifier motos. X means transferred.
    for order, rider_number in enumerate(range(1, 7), 1):
        rows.append(
            row(
                class_id=CLASS_SPLIT,
                class_name="12 Intermediate",
                round_id=ROUND_SPLIT_QUAL,
                round_type_id=123,
                motogroup_id=GROUP_30,
                moto_number=30,
                rider_number=rider_number,
                rider_order=order,
                lane_1=order,
                lane_2=7 - order,
                finish_1="X" if rider_number in {3, 4} else None,
                finish_2="X" if rider_number in {1, 2} else None,
            )
        )
    for order, rider_number in enumerate(range(7, 12), 1):
        rows.append(
            row(
                class_id=CLASS_SPLIT,
                class_name="12 Intermediate",
                round_id=ROUND_SPLIT_QUAL,
                round_type_id=123,
                motogroup_id=GROUP_31,
                moto_number=31,
                rider_number=rider_number,
                rider_order=order,
                lane_1=order,
                lane_2=6 - order,
                finish_1="X" if rider_number in {9, 10} else None,
                finish_2="X" if rider_number in {7, 8} else None,
            )
        )
    final_riders = [1, 2, 3, 4, 7, 8, 9, 10]
    for finish, rider_number in enumerate(final_riders, 1):
        rows.append(
            row(
                class_id=CLASS_SPLIT,
                class_name="12 Intermediate",
                round_id=ROUND_SPLIT_FINAL,
                round_type_id=1,
                motogroup_id=GROUP_FINAL,
                # Deliberately reuses qualifier Moto 30.
                moto_number=30,
                rider_number=rider_number,
                rider_order=finish,
                lane_1=9 - finish,
                finish_1=finish,
            )
        )
    return rows


def total_points_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for order, rider_number in enumerate(range(21, 26), 1):
        rows.append(
            row(
                class_id=CLASS_POINTS,
                class_name="1-2 Balance Bike",
                round_id=ROUND_POINTS_QUAL,
                round_type_id=123,
                motogroup_id=GROUP_POINTS_QUAL,
                moto_number=3,
                rider_number=rider_number,
                rider_order=order,
                lane_1=order,
                lane_2=6 - order,
                lane_3=((order + 1) % 5) + 1,
                finish_1=order,
                finish_2=6 - order,
                finish_3=order,
            )
        )
        rows.append(
            row(
                class_id=CLASS_POINTS,
                class_name="1-2 Balance Bike",
                round_id=ROUND_POINTS_FINAL,
                round_type_id=1,
                motogroup_id=GROUP_POINTS_FINAL,
                moto_number=3,
                rider_number=rider_number,
                rider_order=order,
                lane_1=order,
                finish_1=order,
            )
        )
    return rows


def test_duplicate_moto_number_is_not_collapsed_across_branches() -> None:
    motos = MotoboardService(FakeDatabase(split_class_rows())).list_motos(
        BOARD_ID,
        round_type_id=None,
    )
    same_number = [moto for moto in motos.motos if moto.moto_number == 30]
    assert len(same_number) == 2
    assert {moto.round_type_id for moto in same_number} == {1, 123}
    assert {moto.motogroup_id for moto in same_number} == {GROUP_30, GROUP_FINAL}


def test_split_class_program_resolves_two_rounds_and_exact_main() -> None:
    service = MotoboardService(FakeDatabase(split_class_rows()))
    program = service.get_program(
        BOARD_ID,
        CurrentMoto(moto_number=30, race_phase=RacePhase.ROUND_1),
    )
    assert program.available_phases == [
        RacePhase.ROUND_1,
        RacePhase.ROUND_2,
        RacePhase.MAIN,
    ]
    assert program.qualifier_motogroup_id == GROUP_30
    main = program.stages[-1]
    assert main.round_type_id == 1
    assert main.motogroup_id == GROUP_FINAL
    assert main.moto_number == 30


def test_second_qualifier_group_remains_selectable_by_stable_identity() -> None:
    service = MotoboardService(FakeDatabase(split_class_rows()))
    program = service.get_program(
        BOARD_ID,
        CurrentMoto(
            moto_number=31,
            race_phase=RacePhase.ROUND_2,
            class_id=CLASS_SPLIT,
            qualifier_motogroup_id=GROUP_31,
        ),
    )
    assert program.qualifier_motogroup_id == GROUP_31
    assert program.stages[0].moto_number == 31
    assert program.stages[-1].motogroup_id == GROUP_FINAL


def test_total_points_class_uses_overall_not_main() -> None:
    service = MotoboardService(FakeDatabase(total_points_rows()))
    program = service.get_program(
        BOARD_ID,
        CurrentMoto(moto_number=3, race_phase=RacePhase.ROUND_1),
    )
    assert program.available_phases == [
        RacePhase.ROUND_1,
        RacePhase.ROUND_2,
        RacePhase.ROUND_3,
        RacePhase.OVERALL,
    ]
    assert program.stages[-1].kind == "overall"
    assert program.stages[-1].round_type_id == 1


def test_unavailable_semifinal_is_rejected() -> None:
    service = MotoboardService(FakeDatabase(split_class_rows()))
    with pytest.raises(RacePhaseUnavailableError):
        service.resolve_state(
            BOARD_ID,
            CurrentMoto(moto_number=30, race_phase=RacePhase.SEMIFINAL),
        )


def test_transfer_marker_is_status_not_numeric_finish() -> None:
    assert CurrentResultsService._normalize_finish("X") == (None, True, "Transfer")
    assert CurrentResultsService._normalize_finish(" 2 ") == (2, False, None)


def test_phase_aware_next_moto_preserves_round_and_uses_next_motogroup(tmp_path) -> None:
    from connector.models import CurrentMotoUpdate
    from connector.services.current_moto_service import CurrentMotoService
    from connector.services.race_program_service import RaceProgramService

    class Events:
        def current(self):
            raise AssertionError("Pinned motoboard should avoid latest-event lookup")

    current = CurrentMotoService(tmp_path / "current.json")
    current.set(
        CurrentMotoUpdate(
            moto_number=30,
            race_phase=RacePhase.ROUND_2,
            motoboard_id=BOARD_ID,
            class_id=CLASS_SPLIT,
            round_type_id=123,
            round_id=ROUND_SPLIT_QUAL,
            motogroup_id=GROUP_30,
            qualifier_motogroup_id=GROUP_30,
            round_index=2,
        )
    )
    programs = RaceProgramService(
        current,
        Events(),
        MotoboardService(FakeDatabase(split_class_rows())),
    )

    state = programs.step_moto(1)

    assert state.moto_number == 31
    assert state.race_phase == RacePhase.ROUND_2
    assert state.motogroup_id == GROUP_31
    assert state.qualifier_motogroup_id == GROUP_31
    assert state.round_type_id == 123
