"""Regression coverage derived from the privacy-safe 2026-08-01 export."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

import pytest

from connector.models import CurrentMotoUpdate, Event, RacePhase, ResultsRollStart
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.current_moto_service import CurrentMotoService
from connector.services.current_results_service import CurrentResultsService
from connector.services.motoboard_service import MotoboardService
from connector.services.race_program_service import (
    RaceProgramService,
    RaceSlotUnavailableError,
)
from connector.services.race_slot_service import RaceSlotService
from connector.services.results_roll_service import ResultsRollService
from tests.test_round_aware_program import FakeDatabase, row


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
    motoboards = MotoboardService(FakeDatabase(synthetic_rows()))
    current = CurrentMotoService(tmp_path / "current.json")
    events = GoldCupEvents(board_id)
    programs = RaceProgramService(current, events, motoboards)
    return payload, board_id, motoboards, current, events, programs


def test_fixture_records_complete_observed_main_catalog() -> None:
    payload = fixture()
    assert payload["source"]["contains_rider_personal_data"] is False
    assert [item[0] for item in payload["expected_main_slots"]] == [
        28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
        45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59,
        60, 61, 62,
    ]


def test_gold_cup_window_classifies_29_and_30_as_overall() -> None:
    payload = fixture()
    board_id = UUID(payload["source"]["motoboard_id"])
    slots = RaceSlotService(MotoboardService(FakeDatabase(synthetic_rows())))

    mains = slots.catalog(board_id, RacePhase.MAIN)
    overalls = slots.catalog(board_id, RacePhase.OVERALL)

    assert [(slot.moto_number, slot.class_name) for slot in mains] == [
        (28, "51-55 Novice"),
        (31, "7 Intermediate"),
    ]
    assert [(slot.moto_number, slot.class_name) for slot in overalls] == [
        (29, "5 & Under Intermediate"),
        (30, "6 Intermediate"),
    ]
    assert all(not slot.combined for slot in mains + overalls)


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

    advanced = programs.step_moto(1)
    restored = programs.step_moto(-1)

    assert advanced.moto_number == 31
    assert advanced.race_phase == RacePhase.MAIN
    assert restored.moto_number == 28
    assert restored.race_phase == RacePhase.MAIN
    assert restored.slot_key == original.slot_key
    assert restored.slot_class_ids == original.slot_class_ids
    assert restored.slot_motogroup_ids == original.slot_motogroup_ids


def test_direct_jump_and_results_roll_share_gold_cup_main_slots(tmp_path: Path) -> None:
    _payload, board_id, motoboards, current, events, programs = services(tmp_path)
    current.set(
        CurrentMotoUpdate(
            moto_number=28,
            race_phase=RacePhase.MAIN,
            motoboard_id=board_id,
        )
    )
    with pytest.raises(RaceSlotUnavailableError) as caught:
        programs.select_moto(
            CurrentMotoUpdate(
                moto_number=29,
                race_phase=RacePhase.MAIN,
                motoboard_id=board_id,
            )
        )
    assert caught.value.previous_moto == 28
    assert caught.value.next_moto == 31

    selected = programs.select_moto(
        CurrentMotoUpdate(
            moto_number=31,
            race_phase=RacePhase.MAIN,
            motoboard_id=board_id,
        )
    )
    assert selected.moto_number == 31

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
    assert [item.moto_number for item in results.catalog(board_id)] == [28, 31]

    roll = ResultsRollService(
        current,
        events,
        results,
        tmp_path / "results-roll.json",
    )
    status = roll.start(ResultsRollStart(start_from="first", interval_seconds=10))
    assert status.current_result_moto == 28
    assert status.total_available_results == 2
    assert roll.next().current_result_moto == 31
    assert roll.previous().current_result_moto == 28
    roll.shutdown()
