"""Regression coverage derived from the privacy-safe 2026-08-01 export."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from connector.models import (
    CompetitionStage,
    CurrentMotoUpdate,
    Event,
    FinalizationMethod,
    RacePhase,
    ResultsRollStart,
    ScoringMethod,
)
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_results_service import CurrentResultsService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_program_service import RaceProgramService
from connector.services.race_slot_service import RaceSlotService
from connector.services.results_roll_service import ResultsRollService
from tests.test_round_aware_program import FakeDatabase, row, total_points_rows


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "gold_cup_2026_08_01_race_program.json"
)


def fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def synthetic_rows() -> list[dict[str, object]]:
    """Reproduce only structural evidence, never real rider identities."""
    payload = fixture()
    rows: list[dict[str, object]] = []
    next_rider = 1000
    for entry in payload["classification_window"]:
        qualifier_count = int(entry["qualifier_rider_count"])
        final_count = int(entry["final_rider_count"])
        qualifier_ids = [
            next_rider + index for index in range(qualifier_count)
        ]
        next_rider += 100
        group_ids = [UUID(value) for value in entry["qualifier_motogroup_ids"]]
        groups: list[list[int]] = [[] for _ in group_ids]
        for index, rider_id in enumerate(qualifier_ids):
            groups[index % len(groups)].append(rider_id)
        for group_index, (group_id, rider_ids) in enumerate(zip(group_ids, groups)):
            qualifier_moto = int(entry["displayed_moto"]) + group_index
            for order, rider_id in enumerate(rider_ids, 1):
                scored_rounds = int(entry["qualifier_rounds_scored"])
                rows.append(
                    row(
                        class_id=UUID(entry["class_id"]),
                        class_name=entry["class_name"],
                        round_id=UUID(entry["qualifier_round_id"]),
                        round_type_id=123,
                        motogroup_id=group_id,
                        moto_number=qualifier_moto,
                        rider_number=rider_id,
                        rider_order=order,
                        lane_1=order,
                        lane_2=order if scored_rounds >= 2 else 0,
                        lane_3=order if scored_rounds >= 3 else 0,
                        finish_1=order,
                        finish_2=order if scored_rounds >= 2 else None,
                        finish_3=order if scored_rounds >= 3 else None,
                    )
                )
        for finish, rider_id in enumerate(qualifier_ids[:final_count], 1):
            rows.append(
                row(
                    class_id=UUID(entry["class_id"]),
                    class_name=entry["class_name"],
                    round_id=UUID(entry["final_round_id"]),
                    round_type_id=1,
                    motogroup_id=UUID(entry["final_motogroup_id"]),
                    moto_number=int(entry["displayed_moto"]),
                    rider_number=rider_id,
                    rider_order=finish,
                    lane_1=finish,
                    finish_1=finish,
                )
            )
    return rows


def preceding_gold_cup_total_points_rows() -> list[dict[str, object]]:
    """Sanitized structural analogue of Moto 27 before the proven Main block."""
    class_id = UUID("33502e22-2234-41b6-854d-089bfa2984c8")
    qualifier_round = UUID("6076bdc3-3c0b-423e-86dc-20b99adf8d2f")
    qualifier_group = UUID("387b4732-69fe-4eea-aca7-2f62eea3b725")
    final_round = UUID("1885be9d-7722-4c80-bbb6-7f5222a88477")
    final_group = UUID("cf876391-797d-4f6a-a4ec-d64c53731a3a")
    return [
        {
            **item,
            "class_id": class_id,
            "class_name": "41-45 Novice",
            "round_id": final_round if item["round_type_id"] == 1 else qualifier_round,
            "motogroup_id": final_group if item["round_type_id"] == 1 else qualifier_group,
            "moto_number": 27,
        }
        for item in total_points_rows()
    ]


class GoldCupEvents:
    def __init__(self, board_id: UUID) -> None:
        self.board_id = board_id

    def current(self) -> Event:
        raise AssertionError("The historic Gold Cup event must remain pinned")

    def by_motoboard(self, board_id: UUID) -> Event:
        assert board_id == self.board_id
        return Event(
            event_id=UUID("11111111-1111-1111-1111-111111111111"),
            event_name="Gold Cup / State Race",
            date_begin="2026-08-01",
            race_id=UUID("22222222-2222-2222-2222-222222222222"),
            race_description="Gold Cup / State Race",
            motoboard_id=board_id,
            total_motos=65,
            total_riders=304,
        )


def services(tmp_path: Path):
    payload = fixture()
    board_id = UUID(payload["source"]["motoboard_id"])
    motoboards = gold_cup_motoboards(tmp_path, synthetic_rows())
    current = CurrentMotoService(tmp_path / "current.json")
    events = GoldCupEvents(board_id)
    programs = RaceProgramService(current, events, motoboards)
    return payload, board_id, motoboards, current, events, programs


def gold_cup_motoboards(
    tmp_path: Path,
    rows: list[dict[str, object]],
) -> MotoboardService:
    payload = fixture()
    board_id = UUID(payload["source"]["motoboard_id"])
    service = MotoboardService(
        FakeDatabase(rows),
        phase_override_file=tmp_path / "race-phase-overrides.json",
    )
    service.phase_overrides.set_main_program_start(
        board_id,
        int(payload["main_program_boundary"]["start_moto"]),
    )
    return service


def test_fixture_records_real_gold_cup_main_window_without_rider_data() -> None:
    payload = fixture()
    assert payload["source"]["contains_rider_personal_data"] is False
    assert payload["source"]["safe_export_sha256"] == (
        "5ADCE078C857C20B8716243D2A8B95C837A574C071AC0C4046C3596DC7122E81"
    )
    assert payload["expected_main_window"] == [
        [28, "51-55 Novice"],
        [29, "5 & Under Intermediate"],
        [30, "6 Intermediate"],
        [31, "7 Intermediate"],
    ]
    assert payload["main_program_boundary"]["start_moto"] == 28
    assert payload["main_program_boundary"]["source"] == "operator_override"
    assert payload["main_program_boundary"]["operator_confirmed"] is True


def test_gold_cup_window_is_one_mixed_main_program(tmp_path: Path) -> None:
    payload = fixture()
    board_id = UUID(payload["source"]["motoboard_id"])
    slots = RaceSlotService(gold_cup_motoboards(tmp_path, synthetic_rows()))

    mains = slots.catalog(board_id, RacePhase.MAIN)
    boundary = slots.motoboards.get_main_program_boundary(board_id)

    assert [(slot.moto_number, slot.class_name) for slot in mains] == [
        tuple(item) for item in payload["expected_main_window"]
    ]
    assert all(slot.phase == RacePhase.MAIN for slot in mains)
    assert all(not slot.combined for slot in mains)
    assert boundary.start_moto == 28
    assert boundary.suggested_start_moto == 28
    assert boundary.source.value == "operator_override"
    by_number = {slot.moto_number: slot.members[0].stage for slot in mains}
    assert by_number[28].competition_stage == CompetitionStage.MAIN_EVENT
    assert by_number[28].scoring_method == ScoringMethod.TRANSFER
    assert by_number[29].competition_stage == CompetitionStage.TOTAL_POINTS_FINAL_MOTO
    assert by_number[29].scoring_method == ScoringMethod.TOTAL_POINTS
    assert by_number[29].finalization_method == FinalizationMethod.ACCUMULATED_POINTS
    assert by_number[29].round_index == 3
    assert str(by_number[29].motogroup_id) == payload["classification_window"][1]["physical_motogroup_id"]
    assert str(by_number[29].result_motogroup_id) == payload["classification_window"][1]["final_motogroup_id"]
    assert by_number[30].competition_stage == CompetitionStage.TOTAL_POINTS_FINAL_MOTO
    assert by_number[30].round_index == 1
    assert str(by_number[30].motogroup_id) == payload["classification_window"][2]["physical_motogroup_id"]
    assert by_number[31].competition_stage == CompetitionStage.MAIN_EVENT


def test_gold_cup_total_points_before_main_stays_in_round_three(
    tmp_path: Path,
) -> None:
    payload = fixture()
    board_id = UUID(payload["source"]["motoboard_id"])
    service = RaceSlotService(
        gold_cup_motoboards(
            tmp_path,
            preceding_gold_cup_total_points_rows() + synthetic_rows(),
        )
    )

    assert [slot.moto_number for slot in service.catalog(board_id, RacePhase.MAIN)] == [
        28,
        29,
        30,
        31,
    ]
    round_three = service.catalog(board_id, RacePhase.ROUND_3)
    moto_27 = next(slot for slot in round_three if slot.moto_number == 27)
    assert moto_27.phase == RacePhase.ROUND_3
    assert moto_27.members[0].stage.competition_stage == (
        CompetitionStage.TOTAL_POINTS_FINAL_MOTO
    )


def test_gold_cup_main_next_previous_are_exact_inverses(tmp_path: Path) -> None:
    _payload, board_id, motoboards, current, _events, programs = services(tmp_path)
    slot = RaceSlotService(motoboards).catalog(board_id, RacePhase.MAIN)[0]
    member = slot.members[0]
    current.set(
        CurrentMotoUpdate(
            moto_number=28,
            race_phase=RacePhase.MAIN,
            motoboard_id=board_id,
            class_id=member.stage.class_id,
            round_type_id=1,
            round_id=member.stage.round_id,
            motogroup_id=member.stage.motogroup_id,
            qualifier_motogroup_id=member.qualifier_motogroup_id,
            slot_key=slot.slot_key,
            slot_class_ids=slot.class_ids,
            slot_motogroup_ids=slot.motogroup_ids,
        )
    )
    original = current.get()

    first = programs.step_moto(1)
    second = programs.step_moto(1)
    third = programs.step_moto(1)
    restored_second = programs.step_moto(-1)
    restored_first = programs.step_moto(-1)
    restored = programs.step_moto(-1)

    assert [first.moto_number, second.moto_number, third.moto_number] == [29, 30, 31]
    assert all(
        state.race_phase == RacePhase.MAIN
        for state in (first, second, third, restored_second, restored_first, restored)
    )
    assert [restored_second.moto_number, restored_first.moto_number, restored.moto_number] == [30, 29, 28]
    assert restored.moto_number == 28
    assert restored.race_phase == RacePhase.MAIN
    assert restored.slot_key == original.slot_key
    assert restored.slot_class_ids == original.slot_class_ids
    assert restored.slot_motogroup_ids == original.slot_motogroup_ids


def test_direct_jump_and_results_roll_share_gold_cup_main_slots(tmp_path: Path) -> None:
    payload, board_id, motoboards, current, events, programs = services(tmp_path)
    current.set(
        CurrentMotoUpdate(
            moto_number=28,
            race_phase=RacePhase.MAIN,
            motoboard_id=board_id,
        )
    )
    for expected in (29, 30, 31, 28):
        selected = programs.select_moto(
            CurrentMotoUpdate(
                moto_number=expected,
                race_phase=RacePhase.MAIN,
                motoboard_id=board_id,
            )
        )
        assert selected.moto_number == expected
        assert selected.race_phase == RacePhase.MAIN

    lineups = CurrentLineupService(
        current, events, motoboards, tmp_path / "lineup.json"
    )
    results = CurrentResultsService(
        current,
        events,
        motoboards,
        lineups,
        tmp_path / "results.json",
    )
    catalog = results.catalog(board_id)
    assert [item.moto_number for item in catalog] == [28, 29, 30, 31]
    assert [item.phase_label for item in catalog] == [
        "Main",
        "Total Points Results",
        "Total Points Results",
        "Main",
    ]
    assert len({item.class_id for item in catalog}) == 4
    assert len({(item.moto_number, item.class_id) for item in catalog}) == 4
    assert catalog[1].class_name == "5 & Under Intermediate"
    assert catalog[1].scoring_method == ScoringMethod.TOTAL_POINTS
    assert catalog[1].motogroup_id == UUID(
        payload["classification_window"][1]["final_motogroup_id"]
    )

    roll = ResultsRollService(
        current,
        events,
        results,
        tmp_path / "results-roll.json",
    )
    status = roll.start(ResultsRollStart(start_from="first", interval_seconds=10))
    assert status.current_result_moto == 28
    assert status.total_available_results == 4
    assert roll.next().current_result_moto == 29
    assert roll.next().current_result_moto == 30
    assert roll.next().current_result_moto == 31
    assert roll.previous().current_result_moto == 30
    roll.shutdown()
