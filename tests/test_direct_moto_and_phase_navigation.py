"""Exact moto selection and meaningful phase-transition regressions."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from connector.models import ActiveGraphic, CurrentMotoUpdate, RacePhase
from connector.services.current_moto_service import CurrentMotoService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_program_service import (
    RaceProgramService,
    RaceSlotUnavailableError,
)
from tests.test_race_slots import PinnedEvents, combined_boundary_rows
from tests.test_round_aware_program import (
    BOARD_ID,
    CLASS_NEXT_MAIN,
    CLASS_POINTS,
    CLASS_SPLIT,
    FakeDatabase,
    next_main_rows,
    split_class_rows,
    total_points_rows,
)


def service_for(tmp_path: Path, rows: list[dict[str, object]]) -> RaceProgramService:
    return RaceProgramService(
        CurrentMotoService(tmp_path / "current.json"),
        PinnedEvents(),
        MotoboardService(FakeDatabase(rows)),
    )


def remapped_stage_rows() -> list[dict[str, object]]:
    """One class qualifies at Moto 65 and races its Main at Moto 18."""
    return [
        {
            **item,
            "moto_number": 18 if item["round_type_id"] == 1 else 65,
        }
        for item in split_class_rows()
    ]


def test_go_to_moto_selects_exact_combined_main_and_preserves_state(
    tmp_path: Path,
) -> None:
    programs = service_for(tmp_path, combined_boundary_rows())
    current = programs.current
    current.set(
        CurrentMotoUpdate(
            moto_number=31,
            race_phase=RacePhase.MAIN,
            motoboard_id=BOARD_ID,
            minimum_moto=2,
            maximum_moto=80,
            active_graphic=ActiveGraphic.LINEUP,
        )
    )

    state = programs.select_moto(
        CurrentMotoUpdate(
            moto_number=30,
            race_phase=RacePhase.MAIN,
            motoboard_id=BOARD_ID,
        )
    )

    assert state.moto_number == 30
    assert state.race_phase == RacePhase.MAIN
    assert len(state.slot_class_ids) == 2
    assert " / " in (state.class_name or "")
    assert state.motoboard_id == BOARD_ID
    assert state.minimum_moto == 2
    assert state.maximum_moto == 80
    assert state.active_graphic == ActiveGraphic.LINEUP


def test_go_to_moto_reports_nearest_slots_without_changing_state(
    tmp_path: Path,
) -> None:
    rows = [
        {
            **item,
            "moto_number": 18 if item["round_type_id"] == 1 else 65,
        }
        for item in split_class_rows()
    ]
    rows.extend(
        {
            **item,
            "moto_number": 27 if item["round_type_id"] == 1 else 67,
        }
        for item in next_main_rows()
    )
    programs = service_for(tmp_path, rows)
    original = programs.current.set(
        CurrentMotoUpdate(
            moto_number=18,
            race_phase=RacePhase.MAIN,
            motoboard_id=BOARD_ID,
        )
    )

    with pytest.raises(RaceSlotUnavailableError) as caught:
        programs.select_moto(
            CurrentMotoUpdate(
                moto_number=25,
                race_phase=RacePhase.MAIN,
                motoboard_id=BOARD_ID,
            )
        )

    assert "previous 18" in str(caught.value)
    assert "next 27" in str(caught.value)
    assert programs.current.get() == original


def test_event_change_pins_new_board_and_resolves_nearest_position(
    tmp_path: Path,
) -> None:
    new_board = UUID("99999999-0000-0000-0000-000000000001")
    programs = service_for(tmp_path, remapped_stage_rows())
    programs.current.set(
        CurrentMotoUpdate(
            moto_number=30,
            race_phase=RacePhase.MAIN,
            motoboard_id=BOARD_ID,
        )
    )

    state = programs.select_moto(
        CurrentMotoUpdate(
            moto_number=20,
            race_phase=RacePhase.MAIN,
            motoboard_id=new_board,
        )
    )

    assert state.moto_number == 18
    assert state.motoboard_id == new_board
    assert state.resolved_motoboard_id == new_board
    assert state.navigation_message is not None
    assert "selected event" in state.navigation_message


@pytest.mark.parametrize("moto_number", [0, -1])
def test_go_to_moto_rejects_non_positive_values(moto_number: int) -> None:
    with pytest.raises(ValidationError):
        CurrentMotoUpdate(moto_number=moto_number)


def test_go_to_moto_selects_true_overall_and_keeps_historic_pin(
    tmp_path: Path,
) -> None:
    programs = service_for(tmp_path, total_points_rows())

    state = programs.select_moto(
        CurrentMotoUpdate(
            moto_number=3,
            race_phase=RacePhase.OVERALL,
            motoboard_id=BOARD_ID,
        )
    )

    assert state.moto_number == 3
    assert state.race_phase == RacePhase.OVERALL
    assert state.class_id == CLASS_POINTS
    assert state.motoboard_id == BOARD_ID


def test_round_change_maps_same_class_to_different_moto(tmp_path: Path) -> None:
    programs = service_for(tmp_path, remapped_stage_rows())
    programs.select_moto(
        CurrentMotoUpdate(
            moto_number=65,
            race_phase=RacePhase.ROUND_1,
            motoboard_id=BOARD_ID,
            active_graphic=ActiveGraphic.RESULTS,
        )
    )

    main = programs.select_phase(RacePhase.MAIN)
    qualifier = programs.select_phase(RacePhase.ROUND_1)

    assert main.moto_number == 18
    assert main.race_phase == RacePhase.MAIN
    assert main.class_id == CLASS_SPLIT
    assert main.active_graphic == ActiveGraphic.RESULTS
    assert main.motoboard_id == BOARD_ID
    assert main.navigation_message == "Mapped the selected class to main Moto 18."
    assert qualifier.moto_number == 65
    assert qualifier.race_phase == RacePhase.ROUND_1
    assert qualifier.class_id == CLASS_SPLIT
    assert qualifier.active_graphic == ActiveGraphic.RESULTS


def test_round_change_preserves_combined_class_group(tmp_path: Path) -> None:
    rows = remapped_stage_rows()
    rows.extend(
        {
            **item,
            "moto_number": 18 if item["round_type_id"] == 1 else 3,
        }
        for item in total_points_rows()
    )
    programs = service_for(tmp_path, rows)
    programs.select_moto(
        CurrentMotoUpdate(
            moto_number=65,
            race_phase=RacePhase.ROUND_1,
            motoboard_id=BOARD_ID,
        )
    )

    state = programs.select_phase(RacePhase.MAIN)

    assert state.moto_number == 18
    assert set(state.slot_class_ids) == {CLASS_SPLIT, CLASS_POINTS}
    assert " / " in (state.class_name or "")


def test_round_change_falls_back_when_selected_class_is_absent(
    tmp_path: Path,
) -> None:
    qualifier_only = [
        item for item in split_class_rows() if item["round_type_id"] == 123
    ]
    rows = qualifier_only + next_main_rows()
    programs = service_for(tmp_path, rows)
    programs.select_moto(
        CurrentMotoUpdate(
            moto_number=30,
            race_phase=RacePhase.ROUND_1,
            motoboard_id=BOARD_ID,
        )
    )

    state = programs.select_phase(RacePhase.MAIN)

    assert state.moto_number == 32
    assert state.class_id == CLASS_NEXT_MAIN
    assert state.navigation_message is not None
    assert "selected class is unavailable" in state.navigation_message


def test_first_and_last_moto_in_round_use_slot_boundaries(tmp_path: Path) -> None:
    programs = service_for(tmp_path, combined_boundary_rows())
    programs.select_moto(
        CurrentMotoUpdate(
            moto_number=30,
            race_phase=RacePhase.MAIN,
            motoboard_id=BOARD_ID,
        )
    )

    last = programs.select_phase_boundary(last=True)
    first = programs.select_phase_boundary(last=False)

    assert last.moto_number == 31
    assert last.navigation_message == "Moved to last moto in main."
    assert first.moto_number == 30
    assert first.navigation_message == "Moved to first moto in main."


def test_direct_jump_stale_database_sync_cannot_restore_old_slot(
    tmp_path: Path,
) -> None:
    rows = remapped_stage_rows()
    programs = service_for(tmp_path, rows)
    original = programs.select_moto(
        CurrentMotoUpdate(
            moto_number=65,
            race_phase=RacePhase.ROUND_1,
            motoboard_id=BOARD_ID,
        )
    )
    stale_program = programs.motos.get_program(BOARD_ID, original)
    stale_stage = next(
        stage for stage in stale_program.stages if stage.phase == RacePhase.ROUND_1
    )

    jumped = programs.select_phase(RacePhase.MAIN)
    stale_result = programs.current.sync_race_position(
        motoboard_id=BOARD_ID,
        program=stale_program,
        stage=stale_stage,
        expected_state=original,
    )

    assert jumped.moto_number == 18
    assert stale_result == jumped
    assert programs.current.get() == jumped
