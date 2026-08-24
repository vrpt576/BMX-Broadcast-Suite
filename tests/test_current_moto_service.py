import json
from pathlib import Path
from uuid import UUID

import pytest

from connector.models import (
    ActiveGraphic,
    CompetitionStage,
    CurrentMotoUpdate,
    FinalizationMethod,
    RacePhase,
    RaceProgram,
    RaceStage,
    ScoringMethod,
)
from connector.services.current_moto_service import (
    CurrentMotoService,
    CurrentMotoValidationError,
)


def service(tmp_path: Path) -> CurrentMotoService:
    return CurrentMotoService(tmp_path / "current.json")


def test_defaults_to_moto_one(tmp_path: Path) -> None:
    state = service(tmp_path).get()
    assert state.moto_number == 1
    assert state.maximum_moto is None
    assert state.race_phase == RacePhase.ROUND_1
    assert state.class_name is None


def test_next_previous_and_persistence(tmp_path: Path) -> None:
    first = service(tmp_path)
    assert first.next().moto_number == 2
    assert first.next().moto_number == 3
    assert first.previous().moto_number == 2

    restarted = service(tmp_path)
    assert restarted.get().moto_number == 2


def test_respects_maximum_moto(tmp_path: Path) -> None:
    current = service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=3, maximum_moto=3))
    assert current.next().moto_number == 3


def test_rejects_out_of_range_moto(tmp_path: Path) -> None:
    current = service(tmp_path)
    with pytest.raises(CurrentMotoValidationError):
        current.set(CurrentMotoUpdate(moto_number=5, maximum_moto=4))


def test_round_progression_and_persistence(tmp_path: Path) -> None:
    current = service(tmp_path)
    assert current.next_phase().race_phase == RacePhase.ROUND_2
    assert current.next_phase().race_phase == RacePhase.ROUND_3
    assert current.next_phase().race_phase == RacePhase.QUARTERFINAL
    assert current.next_phase().race_phase == RacePhase.SEMIFINAL
    assert current.next_phase().race_phase == RacePhase.MAIN
    assert current.next_phase().race_phase == RacePhase.MAIN

    restarted = service(tmp_path)
    assert restarted.get().race_phase == RacePhase.MAIN
    assert restarted.previous_phase().race_phase == RacePhase.SEMIFINAL


def test_can_set_phase_without_changing_moto(tmp_path: Path) -> None:
    current = service(tmp_path)
    state = current.set(CurrentMotoUpdate(moto_number=12, race_phase=RacePhase.SEMIFINAL))
    assert state.moto_number == 12
    assert state.race_phase == RacePhase.SEMIFINAL


def test_class_name_is_saved_normalized_and_persisted(tmp_path: Path) -> None:
    current = service(tmp_path)
    state = current.set(
        CurrentMotoUpdate(
            moto_number=8,
            race_phase=RacePhase.MAIN,
            class_name="  17-20   Expert  ",
        )
    )
    assert state.class_name == "17-20 Expert"
    assert current.next().class_name == "17-20 Expert"
    assert service(tmp_path).get().class_name == "17-20 Expert"


def test_blank_class_name_clears_class(tmp_path: Path) -> None:
    current = service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=1, class_name="51-55 Cruiser"))
    state = current.set(CurrentMotoUpdate(moto_number=1, class_name="   "))
    assert state.class_name is None


def test_rejects_overlong_class_name(tmp_path: Path) -> None:
    current = service(tmp_path)
    with pytest.raises(CurrentMotoValidationError):
        current.set(CurrentMotoUpdate(moto_number=1, class_name="x" * 101))


def test_v03_state_without_class_name_remains_compatible(tmp_path: Path) -> None:
    state_file = tmp_path / "current.json"
    state_file.write_text(
        '{"moto_number": 4, "race_phase": "round_2", "minimum_moto": 1, "maximum_moto": null, "updated_at": null, "source": "manual"}',
        encoding="utf-8",
    )
    state = CurrentMotoService(state_file).get()
    assert state.moto_number == 4
    assert state.race_phase == RacePhase.ROUND_2
    assert state.class_name is None


def test_reset_clears_class_name(tmp_path: Path) -> None:
    current = service(tmp_path)
    current.set(CurrentMotoUpdate(moto_number=5, race_phase=RacePhase.MAIN, class_name="11 Expert"))
    state = current.reset()
    assert state.moto_number == 1
    assert state.race_phase == RacePhase.ROUND_1
    assert state.class_name is None


def test_graphic_selection_persists_and_moto_steps_preserve_it(tmp_path: Path) -> None:
    current = service(tmp_path)
    state = current.set_graphic(ActiveGraphic.LINEUP)
    assert state.active_graphic == ActiveGraphic.LINEUP
    assert current.next().active_graphic == ActiveGraphic.LINEUP
    assert service(tmp_path).get().active_graphic == ActiveGraphic.LINEUP


def test_reset_restores_current_moto_graphic(tmp_path: Path) -> None:
    current = service(tmp_path)
    current.set_graphic(ActiveGraphic.HIDDEN)
    assert current.reset().active_graphic == ActiveGraphic.CURRENT_MOTO


def test_old_state_without_active_graphic_remains_compatible(tmp_path: Path) -> None:
    state_file = tmp_path / "current.json"
    state_file.write_text(
        '{"moto_number": 9, "race_phase": "main", "minimum_moto": 1, "maximum_moto": null, "updated_at": null, "source": "manual"}',
        encoding="utf-8",
    )
    state = CurrentMotoService(state_file).get()
    assert state.active_graphic == ActiveGraphic.CURRENT_MOTO


def test_legacy_overall_state_migrates_to_main_without_losing_selection(tmp_path: Path) -> None:
    state_file = tmp_path / "current.json"
    state_file.write_text(
        '{"moto_number":29,"race_phase":"overall","phase_label":"Overall",'
        '"class_name":"5 & Under Intermediate","minimum_moto":1,'
        '"maximum_moto":65,"motoboard_id":"10000000-0000-0000-0000-000000000001",'
        '"class_id":"20000000-0000-0000-0000-000000000029",'
        '"slot_key":"legacy:overall:29","active_graphic":"results"}',
        encoding="utf-8",
    )

    state = CurrentMotoService(state_file).get()

    assert state.moto_number == 29
    assert state.race_phase == RacePhase.MAIN
    assert state.phase_label == "Main"
    assert state.class_name == "5 & Under Intermediate"
    assert state.maximum_moto == 65
    assert state.motoboard_id == UUID("10000000-0000-0000-0000-000000000001")
    assert state.class_id == UUID("20000000-0000-0000-0000-000000000029")
    assert state.slot_key is None
    assert state.active_graphic == ActiveGraphic.RESULTS


def test_legacy_round_3_label_is_dropped_without_guessing_the_replacement(
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "current.json"
    state_file.write_text(
        '{"moto_number":39,"race_phase":"round_3","phase_label":"Round 3",'
        '"class_name":"14 Intermediate","minimum_moto":1,'
        '"maximum_moto":65,"motoboard_id":"10000000-0000-0000-0000-000000000001",'
        '"class_id":"20000000-0000-0000-0000-000000000039",'
        '"slot_key":"legacy:round_3:39","active_graphic":"current_moto"}',
        encoding="utf-8",
    )

    state = CurrentMotoService(state_file).get()

    assert state.moto_number == 39
    assert state.race_phase == RacePhase.ROUND_3
    assert state.phase_label is None
    assert state.slot_key is None
    assert state.class_name == "14 Intermediate"
    assert state.motoboard_id == UUID("10000000-0000-0000-0000-000000000001")


@pytest.mark.parametrize("label", ["round 3", "ROUND 3", "  Round 3  "])
def test_legacy_round_3_label_is_dropped_case_and_whitespace_insensitively(
    tmp_path: Path, label: str
) -> None:
    state_file = tmp_path / "current.json"
    payload = json.dumps(
        {
            "moto_number": 39,
            "race_phase": "round_3",
            "phase_label": label,
            "minimum_moto": 1,
            "slot_key": "legacy:round_3:39",
        }
    )
    state_file.write_text(payload, encoding="utf-8")

    state = CurrentMotoService(state_file).get()

    assert state.phase_label is None
    assert state.slot_key is None


@pytest.mark.parametrize("label", ["Main", "Moto 3"])
def test_a_current_round_3_label_is_preserved_untouched(
    tmp_path: Path, label: str
) -> None:
    state_file = tmp_path / "current.json"
    payload = json.dumps(
        {
            "moto_number": 39,
            "race_phase": "round_3",
            "phase_label": label,
            "minimum_moto": 1,
            "slot_key": "some-motoboard:round_3:39",
        }
    )
    state_file.write_text(payload, encoding="utf-8")

    state = CurrentMotoService(state_file).get()

    assert state.phase_label == label
    assert state.slot_key == "some-motoboard:round_3:39"


def test_manual_selection_change_clears_stale_classification_metadata(tmp_path: Path) -> None:
    current = service(tmp_path)
    current.set(
        CurrentMotoUpdate(
            moto_number=29,
            race_phase=RacePhase.MAIN,
            competition_stage=CompetitionStage.TOTAL_POINTS_FINAL_MOTO,
            scoring_method=ScoringMethod.TOTAL_POINTS,
            finalization_method=FinalizationMethod.ACCUMULATED_POINTS,
        )
    )

    state = current.set(CurrentMotoUpdate(moto_number=30))

    assert state.competition_stage == CompetitionStage.UNKNOWN
    assert state.scoring_method == ScoringMethod.UNKNOWN
    assert state.finalization_method == FinalizationMethod.UNKNOWN


def test_stale_background_resolution_cannot_undo_newer_moto(tmp_path: Path) -> None:
    current = service(tmp_path)
    board_id = UUID("10000000-0000-0000-0000-000000000001")
    old_class_id = UUID("20000000-0000-0000-0000-000000000025")
    new_class_id = UUID("20000000-0000-0000-0000-000000000027")
    old_round_id = UUID("30000000-0000-0000-0000-000000000025")
    new_round_id = UUID("30000000-0000-0000-0000-000000000027")
    old_group_id = UUID("40000000-0000-0000-0000-000000000025")
    new_group_id = UUID("40000000-0000-0000-0000-000000000027")

    current.set(
        CurrentMotoUpdate(
            moto_number=25,
            race_phase=RacePhase.MAIN,
            motoboard_id=board_id,
            class_id=old_class_id,
            round_type_id=1,
            round_id=old_round_id,
            motogroup_id=old_group_id,
            round_index=1,
            active_graphic=ActiveGraphic.LINEUP,
        )
    )
    stale_snapshot = current.get()

    def context(
        moto_number: int,
        class_id: UUID,
        round_id: UUID,
        group_id: UUID,
        class_name: str,
    ) -> tuple[RaceProgram, RaceStage]:
        stage = RaceStage(
            phase=RacePhase.MAIN,
            label="Main",
            kind="main",
            moto_number=moto_number,
            class_id=class_id,
            class_name=class_name,
            round_type_id=1,
            round_id=round_id,
            motogroup_id=group_id,
            round_index=1,
        )
        return (
            RaceProgram(
                motoboard_id=board_id,
                class_id=class_id,
                class_name=class_name,
                stages=[stage],
                available_phases=[RacePhase.MAIN],
            ),
            stage,
        )

    new_program, new_stage = context(
        27, new_class_id, new_round_id, new_group_id, "7 Intermediate"
    )
    advanced = current.sync_race_position(
        motoboard_id=board_id,
        program=new_program,
        stage=new_stage,
        expected_state=stale_snapshot,
    )

    old_program, old_stage = context(
        25, old_class_id, old_round_id, old_group_id, "5 & Under Intermediate"
    )
    stale_result = current.sync_race_position(
        motoboard_id=board_id,
        program=old_program,
        stage=old_stage,
        expected_state=stale_snapshot,
    )

    assert advanced.moto_number == 27
    assert advanced.race_phase == RacePhase.MAIN
    assert advanced.active_graphic == ActiveGraphic.LINEUP

    stable_result = current.sync_race_position(
        motoboard_id=board_id,
        program=new_program,
        stage=new_stage,
        expected_state=advanced,
    )

    assert stable_result == advanced
    assert stale_result == advanced
    assert current.get() == advanced
