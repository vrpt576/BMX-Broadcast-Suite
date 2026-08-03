"""Scoring classification must remain separate from program navigation."""

from __future__ import annotations

import json
from uuid import UUID

from connector.models import (
    CompetitionStage,
    CurrentMoto,
    FinalizationMethod,
    RacePhase,
    RaceProgram,
    RaceStage,
    ScoringMethod,
)
from connector.services.motoboard_service import MotoboardService
from connector.services.phase_classification_service import (
    PhaseClassificationOverrideStore,
    classify_final,
)
from tests.test_round_aware_program import (
    BOARD_ID,
    CLASS_POINTS,
    FakeDatabase,
    GROUP_POINTS_QUAL,
    GROUP_POINTS_FINAL,
    split_class_rows,
    total_points_rows,
)


def _branches(rows):
    motos = MotoboardService(FakeDatabase(rows)).list_motos(
        BOARD_ID,
        round_type_id=None,
    ).motos
    return (
        [moto for moto in motos if moto.round_type_id == 123],
        [moto for moto in motos if moto.round_type_id == 1],
    )


def test_transfer_final_uses_main_program_and_final_race_results() -> None:
    qualifiers, finals = _branches(split_class_rows())

    decision = classify_final(qualifiers, finals)

    assert decision.program_segment == RacePhase.MAIN
    assert decision.competition_stage == CompetitionStage.MAIN_EVENT
    assert decision.scoring_method == ScoringMethod.TRANSFER
    assert decision.finalization_method == FinalizationMethod.FINAL_RACE
    assert decision.reason == "multiple_qualifier_motogroups_feed_final"
    assert decision.ambiguous is False


def test_total_points_classification_is_metadata_not_overall_navigation() -> None:
    qualifiers, finals = _branches(total_points_rows())

    decision = classify_final(qualifiers, finals)

    assert "overall" not in {phase.value for phase in RacePhase}
    assert decision.program_segment == RacePhase.MAIN
    assert decision.competition_stage == CompetitionStage.TOTAL_POINTS_CLASSIFICATION
    assert decision.scoring_method == ScoringMethod.TOTAL_POINTS
    assert decision.finalization_method == FinalizationMethod.ACCUMULATED_POINTS
    assert decision.reason == "same_riders_with_accumulated_round_scores"
    assert decision.ambiguous is False


def test_class_without_final_has_no_final_program_occurrence() -> None:
    qualifiers, finals = _branches(total_points_rows())

    decision = classify_final(qualifiers, [])

    assert decision.program_segment is None
    assert decision.competition_stage == CompetitionStage.UNKNOWN
    assert decision.scoring_method == ScoringMethod.UNKNOWN
    assert decision.finalization_method == FinalizationMethod.UNKNOWN


def test_total_points_third_moto_stays_round_three_without_main_block_evidence() -> None:
    service = MotoboardService(FakeDatabase(total_points_rows()))

    program = service.get_program(
        BOARD_ID,
        CurrentMoto(
            moto_number=3,
            race_phase=RacePhase.MAIN,
            class_id=CLASS_POINTS,
        ),
    )

    assert program.available_phases == [
        RacePhase.ROUND_1,
        RacePhase.ROUND_2,
        RacePhase.ROUND_3,
    ]
    stage = program.stages[-1]
    assert stage.phase == RacePhase.ROUND_3
    assert stage.label == "Round 3"
    assert stage.competition_stage == CompetitionStage.TOTAL_POINTS_FINAL_MOTO
    assert stage.scoring_method == ScoringMethod.TOTAL_POINTS
    assert stage.finalization_method == FinalizationMethod.ACCUMULATED_POINTS
    assert stage.motogroup_id == GROUP_POINTS_QUAL
    assert stage.round_index == 3
    assert stage.result_motogroup_id == GROUP_POINTS_FINAL
    assert stage.result_round_index == 1
    assert all(
        item.competition_stage != CompetitionStage.MAIN_EVENT
        for item in program.stages
    )


def test_advanced_transfer_program_keeps_quarter_semi_and_main_as_segments() -> None:
    class_id = UUID("81000000-0000-0000-0000-000000000001")
    phases = [
        (RacePhase.ROUND_1, CompetitionStage.QUALIFYING_MOTO_1),
        (RacePhase.ROUND_2, CompetitionStage.QUALIFYING_MOTO_2),
        (RacePhase.QUARTERFINAL, CompetitionStage.QUARTER),
        (RacePhase.SEMIFINAL, CompetitionStage.SEMI),
        (RacePhase.MAIN, CompetitionStage.MAIN_EVENT),
    ]
    stages = [
        RaceStage(
            phase=phase,
            label={
                RacePhase.ROUND_1: "Round 1",
                RacePhase.ROUND_2: "Round 2",
                RacePhase.QUARTERFINAL: "Quarterfinals",
                RacePhase.SEMIFINAL: "Semifinals",
                RacePhase.MAIN: "Main",
            }[phase],
            kind=competition_stage.value,
            moto_number=40 + index,
            class_id=class_id,
            class_name="Synthetic Advanced Transfer",
            round_type_id=200 + index,
            round_id=UUID(f"82000000-0000-0000-0000-{index:012d}"),
            motogroup_id=UUID(f"83000000-0000-0000-0000-{index:012d}"),
            round_index=1,
            competition_stage=competition_stage,
            scoring_method=ScoringMethod.TRANSFER,
            finalization_method=FinalizationMethod.FINAL_RACE,
        )
        for index, (phase, competition_stage) in enumerate(phases, 1)
    ]
    program = RaceProgram(
        motoboard_id=BOARD_ID,
        class_id=class_id,
        class_name="Synthetic Advanced Transfer",
        stages=stages,
        available_phases=[phase for phase, _ in phases],
    )

    assert program.available_phases == [phase for phase, _ in phases]
    assert [stage.competition_stage for stage in program.stages] == [
        competition_stage for _, competition_stage in phases
    ]
    assert all(stage.scoring_method == ScoringMethod.TRANSFER for stage in stages)
    assert "overall" not in {phase.value for phase in program.available_phases}


def test_legacy_overall_override_selects_accumulated_points_not_a_phase(tmp_path) -> None:
    path = tmp_path / "race_phase_overrides.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "events": {
                    str(BOARD_ID): {
                        "classes": {str(CLASS_POINTS): "overall"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    override = PhaseClassificationOverrideStore(path).get(
        BOARD_ID,
        CLASS_POINTS,
        GROUP_POINTS_FINAL,
    )
    qualifiers, finals = _branches(total_points_rows())

    decision = classify_final(qualifiers, finals, override=override)

    assert decision.program_segment == RacePhase.MAIN
    assert decision.finalization_method == FinalizationMethod.ACCUMULATED_POINTS
    assert decision.overridden is True
    assert decision.reason == "event_specific_operator_override"
