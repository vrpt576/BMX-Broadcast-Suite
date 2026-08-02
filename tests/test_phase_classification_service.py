"""Regression coverage for deterministic Main/Overall interpretation."""

from __future__ import annotations

import json

from connector.models import CurrentMoto, RacePhase
from connector.services.motoboard_service import MotoboardService
from connector.services.phase_classification_service import (
    FinalClassification,
    PhaseClassificationOverrideStore,
    classify_final,
)
from tests.test_round_aware_program import (
    BOARD_ID,
    CLASS_POINTS,
    FakeDatabase,
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


def test_qualifiers_feeding_a_separately_raced_main_are_main() -> None:
    qualifiers, finals = _branches(split_class_rows())

    decision = classify_final(qualifiers, finals)

    assert decision.classification == FinalClassification.MAIN
    assert decision.phase == RacePhase.MAIN
    assert decision.reason == "multiple_qualifier_motogroups_feed_final"
    assert decision.ambiguous is False


def test_accumulated_points_classification_remains_overall() -> None:
    qualifiers, finals = _branches(total_points_rows())

    decision = classify_final(qualifiers, finals)

    assert decision.classification == FinalClassification.OVERALL
    assert decision.phase == RacePhase.OVERALL
    assert decision.reason == "same_riders_with_accumulated_round_scores"
    assert decision.ambiguous is False


def test_standalone_final_is_main_and_class_without_final_has_no_main() -> None:
    qualifiers, finals = _branches(total_points_rows())

    standalone = classify_final([], finals)
    no_final = classify_final(qualifiers, [])

    assert standalone.classification == FinalClassification.MAIN
    assert standalone.reason == "standalone_final_without_qualifier_branch"
    assert no_final.classification == FinalClassification.NONE
    assert no_final.phase is None


def test_anonymized_gold_cup_combined_shape_is_one_main_classification() -> None:
    qualifiers, finals = _branches(total_points_rows())

    decision = classify_final(qualifiers, finals, combined_final=True)

    assert decision.classification == FinalClassification.MAIN
    assert decision.reason == "multiple_classes_share_final_moto"


def test_separate_final_moto_is_main_even_with_same_riders() -> None:
    rows = total_points_rows()
    for row in rows:
        if row["round_type_id"] == 1:
            row["moto_number"] = 99
    qualifiers, finals = _branches(rows)

    decision = classify_final(qualifiers, finals)

    assert decision.classification == FinalClassification.MAIN
    assert decision.reason == "final_uses_separate_displayed_moto"


def test_ambiguous_same_slot_shape_is_reported_and_can_be_overridden(tmp_path) -> None:
    rows = total_points_rows()
    for row in rows:
        if row["round_type_id"] == 123:
            row["finish_1"] = 1
            row["finish_2"] = None
            row["finish_3"] = None
    qualifiers, finals = _branches(rows)
    decision = classify_final(qualifiers, finals)
    assert decision.classification == FinalClassification.OVERALL
    assert decision.ambiguous is True

    path = tmp_path / "race_phase_overrides.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "events": {
                    str(BOARD_ID): {
                        "classes": {str(CLASS_POINTS): "main"},
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
    overridden = classify_final(qualifiers, finals, override=override)

    assert overridden.classification == FinalClassification.MAIN
    assert overridden.overridden is True
    assert overridden.reason == "event_specific_operator_override"


def test_program_applies_event_specific_main_override(tmp_path) -> None:
    path = tmp_path / "race_phase_overrides.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "events": {
                    str(BOARD_ID): {
                        "motogroups": {str(GROUP_POINTS_FINAL): "main"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    service = MotoboardService(
        FakeDatabase(total_points_rows()),
        phase_override_file=path,
    )

    program = service.get_program(
        BOARD_ID,
        CurrentMoto(
            moto_number=3,
            race_phase=RacePhase.MAIN,
            class_id=CLASS_POINTS,
        ),
    )

    final = program.stages[-1]
    assert final.phase == RacePhase.MAIN
    assert final.label == "Main"
    assert final.classification_overridden is True
    assert final.classification_reason == "event_specific_operator_override"
