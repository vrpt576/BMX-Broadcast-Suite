"""Unique combined-slot navigation and Results Roll catalog coverage."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from connector.models import CurrentMotoUpdate, RacePhase
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_results_service import CurrentResultsService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_program_service import RaceProgramService
from connector.services.race_slot_service import RaceSlotService
from tests.test_round_aware_program import (
    BOARD_ID,
    CLASS_SPLIT,
    FakeDatabase,
    GROUP_30,
    GROUP_FINAL,
    ROUND_SPLIT_FINAL,
    next_main_rows,
    split_class_rows,
    total_points_rows,
)


class PinnedEvents:
    def current(self):
        raise AssertionError("Pinned historic event must not resolve latest event")

    def by_motoboard(self, _board_id):
        raise LookupError


def combined_boundary_rows() -> list[dict[str, object]]:
    rows = split_class_rows()
    rows.extend({**item, "moto_number": 30} for item in total_points_rows())
    rows.extend({**item, "moto_number": 31} for item in next_main_rows())
    return rows


def four_class_combined_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    template = next_main_rows()
    for variant in range(1, 5):
        class_id = UUID(f"71000000-0000-0000-0000-{variant:012d}")
        qualifier_round = UUID(f"72000000-0000-0000-0000-{variant:012d}")
        final_round = UUID(f"73000000-0000-0000-0000-{variant:012d}")
        qualifier_group = UUID(f"74000000-0000-0000-0000-{variant:012d}")
        final_group = UUID(f"75000000-0000-0000-0000-{variant:012d}")
        for item in template:
            is_final = item["round_type_id"] == 1
            rows.append(
                {
                    **item,
                    "class_id": class_id,
                    "class_name": f"Combined Fixture Class {variant}",
                    "class_name_short": f"Fixture {variant}",
                    "round_id": final_round if is_final else qualifier_round,
                    "motogroup_id": final_group if is_final else qualifier_group,
                    "moto_number": 50,
                }
            )
    return rows


def test_two_classes_share_one_main_slot_and_next_previous_are_symmetric(
    tmp_path: Path,
) -> None:
    database = FakeDatabase(combined_boundary_rows())
    motoboards = MotoboardService(database)
    slots = RaceSlotService(motoboards).catalog(BOARD_ID, RacePhase.MAIN)
    assert [slot.moto_number for slot in slots] == [30, 31]
    assert slots[0].combined is True
    assert len(slots[0].class_ids) == 2

    current = CurrentMotoService(tmp_path / "current.json")
    current.set(
        CurrentMotoUpdate(
            moto_number=30,
            race_phase=RacePhase.MAIN,
            motoboard_id=BOARD_ID,
            class_id=CLASS_SPLIT,
            round_type_id=1,
            round_id=ROUND_SPLIT_FINAL,
            motogroup_id=GROUP_FINAL,
            qualifier_motogroup_id=GROUP_30,
        )
    )
    original = current.get()
    programs = RaceProgramService(current, PinnedEvents(), motoboards)

    advanced = programs.step_moto(1)
    stale_program = motoboards.get_program(BOARD_ID, original)
    stale_stage = next(
        stage for stage in stale_program.stages if stage.phase == RacePhase.MAIN
    )
    stale_result = current.sync_race_position(
        motoboard_id=BOARD_ID,
        program=stale_program,
        stage=stale_stage,
        expected_state=original,
    )
    restored = programs.step_moto(-1)

    assert advanced.moto_number == 31
    assert stale_result == advanced
    assert restored.moto_number == 30
    assert restored.slot_key == slots[0].slot_key
    assert restored.slot_class_ids == slots[0].class_ids
    assert restored.slot_motogroup_ids == slots[0].motogroup_ids
    assert restored.class_name == slots[0].class_name
    assert restored.motoboard_id == BOARD_ID


def test_four_classification_rows_collapse_to_one_slot() -> None:
    service = MotoboardService(FakeDatabase(four_class_combined_rows()))

    slots = RaceSlotService(service).catalog(BOARD_ID, RacePhase.MAIN)

    assert len(slots) == 1
    assert slots[0].moto_number == 50
    assert slots[0].combined is True
    assert len(slots[0].members) == 4
    assert len(slots[0].class_ids) == 4


def test_results_catalog_uses_same_combined_slot_order(tmp_path: Path) -> None:
    database = FakeDatabase(four_class_combined_rows())
    motoboards = MotoboardService(database)
    current = CurrentMotoService(tmp_path / "current.json")
    lineups = CurrentLineupService(
        current,
        PinnedEvents(),
        motoboards,
        tmp_path / "lineup.json",
    )
    results = CurrentResultsService(
        current,
        PinnedEvents(),
        motoboards,
        lineups,
        tmp_path / "results.json",
    )

    catalog = results.catalog(BOARD_ID, event_name="Anonymized Gold Cup Fixture")

    assert len(catalog) == 1
    assert catalog[0].moto_number == 50
    assert catalog[0].progress_index == 1
    assert catalog[0].progress_total == 1
    assert all(
        f"Combined Fixture Class {number}" in catalog[0].class_name
        for number in range(1, 5)
    )


def test_slot_boundaries_do_not_wrap(tmp_path: Path) -> None:
    database = FakeDatabase(combined_boundary_rows())
    motoboards = MotoboardService(database)
    slots = RaceSlotService(motoboards).catalog(BOARD_ID, RacePhase.MAIN)
    last = slots[-1]
    member = last.members[0]
    current = CurrentMotoService(tmp_path / "current.json")
    current.set(
        CurrentMotoUpdate(
            moto_number=last.moto_number,
            race_phase=last.phase,
            motoboard_id=BOARD_ID,
            class_id=member.stage.class_id,
            round_type_id=member.stage.round_type_id,
            round_id=member.stage.round_id,
            motogroup_id=member.stage.motogroup_id,
            qualifier_motogroup_id=member.qualifier_motogroup_id,
            slot_key=last.slot_key,
            slot_class_ids=last.class_ids,
            slot_motogroup_ids=last.motogroup_ids,
        )
    )
    programs = RaceProgramService(current, PinnedEvents(), motoboards)

    assert programs.step_moto(1) == current.get()

    first = slots[0]
    first_member = first.members[0]
    current.set(
        CurrentMotoUpdate(
            moto_number=first.moto_number,
            race_phase=first.phase,
            motoboard_id=BOARD_ID,
            class_id=first_member.stage.class_id,
            round_type_id=first_member.stage.round_type_id,
            round_id=first_member.stage.round_id,
            motogroup_id=first_member.stage.motogroup_id,
            qualifier_motogroup_id=first_member.qualifier_motogroup_id,
            slot_key=first.slot_key,
            slot_class_ids=first.class_ids,
            slot_motogroup_ids=first.motogroup_ids,
        )
    )
    assert programs.step_moto(-1) == current.get()
