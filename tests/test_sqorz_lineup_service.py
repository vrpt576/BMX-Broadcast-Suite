"""Sqorz-only lineup building -- reuses CurrentLineup/LineupRider unchanged
(connector/models.py) and never imports sqorz_matching.py, since there is
exactly one source of rider data here, not two to reconcile. Tested against
the real captured fixture used throughout 1.3.2's navigation work.
"""

from __future__ import annotations

import json
from pathlib import Path

from connector.models import RacePhase
from connector.services.sqorz_lineup_service import (
    build_sqorz_only_lineup,
    empty_sqorz_only_lineup,
)
from connector.services.sqorz_navigation_service import SqorzRaceSlot, build_class_phase_sequence
from connector.services.sqorz_service import SqorzRiderTime, parse_event_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def load_real_riders() -> list[SqorzRiderTime]:
    payload = json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))
    return parse_event_payload(payload)


def riders_for(all_riders, class_code, phase_code):
    return [r for r in all_riders if r.class_code == class_code and r.phase_code == phase_code]


def rider(**overrides) -> SqorzRiderTime:
    defaults = dict(
        class_code="C1",
        class_name="Test Class",
        plate="1",
        first_name="A",
        last_name="RIDER",
        transponder=None,
        phase_code="M1",
        phase_name="Moto 1",
        time_seconds=None,
        time_raw=None,
        race_position=None,
        rank=None,
        result=None,
    )
    defaults.update(overrides)
    return SqorzRiderTime(**defaults)


# ---------------------------------------------------------------------------
# build_sqorz_only_lineup -- real data
# ---------------------------------------------------------------------------


def test_lineup_for_a_real_moto_uses_sqorz_phase_name_as_the_round_label() -> None:
    """The core round-label rule, direction 2: with no RaceManager at all,
    Sqorz's own phase name IS the round label -- never invented, never
    left blank when Sqorz actually supplied one."""
    all_riders = load_real_riders()
    slot = next(s for s in build_class_phase_sequence(all_riders, "308") if s.phase_code == "M1")

    lineup = build_sqorz_only_lineup(riders_for(all_riders, "308", "M1"), slot)

    assert lineup.phase_label == "Moto 1"
    assert lineup.class_name == "12 Expert"
    assert lineup.sqorz_phase_code == "M1"
    assert lineup.source == "sqorz"


def test_lineup_for_the_semi_final_carries_its_own_real_label() -> None:
    all_riders = load_real_riders()
    slot = next(s for s in build_class_phase_sequence(all_riders, "308") if s.phase_code == "2F")

    lineup = build_sqorz_only_lineup(riders_for(all_riders, "308", "2F"), slot)

    assert lineup.phase_label == "Semi Final"
    assert lineup.race_phase == RacePhase.SEMIFINAL  # coarse categorisation only
    assert lineup.moto_number == 2  # derived from "2F", not a RaceManager moto number


def test_lineup_riders_carry_real_times_and_plates() -> None:
    all_riders = load_real_riders()
    rows = riders_for(all_riders, "308", "M1")
    slot = next(s for s in build_class_phase_sequence(all_riders, "308") if s.phase_code == "M1")

    lineup = build_sqorz_only_lineup(rows, slot)

    assert len(lineup.riders) == len(rows)
    assert any(r.time_seconds is not None for r in lineup.riders)
    assert all(r.bike_number is not None for r in lineup.riders)
    assert all(r.last_name for r in lineup.riders)


def test_lineup_riders_are_sorted_by_gate_then_last_name() -> None:
    rows = [
        rider(plate="1", last_name="ZEBRA", race_position=3),
        rider(plate="2", last_name="APPLE", race_position=1),
        rider(plate="3", last_name="MIDDLE", race_position=None),
    ]
    slot = SqorzRaceSlot(
        class_code="C1", class_name="Test Class", phase_code="M1", phase_name="Moto 1", has_recorded_time=False
    )

    lineup = build_sqorz_only_lineup(rows, slot)

    assert [r.last_name for r in lineup.riders] == ["APPLE", "ZEBRA", "MIDDLE"]


def test_lineup_only_shows_plausible_finishes_not_raw_status_codes() -> None:
    """result=100400 is a real observed Sqorz status code (withdrawn), not
    a finish position -- must render exactly like a missing finish, never
    a fabricated placement. See plausible_finish() in sqorz_service.py."""
    rows = [rider(plate="1", last_name="A", result=2), rider(plate="2", last_name="B", result=100400)]
    slot = SqorzRaceSlot(
        class_code="C1", class_name="Test Class", phase_code="M1", phase_name="Moto 1", has_recorded_time=False
    )

    lineup = build_sqorz_only_lineup(rows, slot)

    finishes = {r.last_name: r.finish for r in lineup.riders}
    assert finishes["A"] == 2
    assert finishes["B"] is None


def test_lineup_gate_comes_from_sqorz_race_position() -> None:
    rows = [rider(plate="1", last_name="A", race_position=4)]
    slot = SqorzRaceSlot(
        class_code="C1", class_name="Test Class", phase_code="M1", phase_name="Moto 1", has_recorded_time=False
    )

    lineup = build_sqorz_only_lineup(rows, slot)

    assert lineup.riders[0].gate == 4


def test_lineup_class_name_falls_back_when_slot_has_none() -> None:
    slot = SqorzRaceSlot(
        class_code="C1", class_name=None, phase_code="M1", phase_name="Moto 1", has_recorded_time=False
    )
    lineup = build_sqorz_only_lineup([], slot)
    assert lineup.class_name == "Class not set"


def test_lineup_available_phases_is_always_empty() -> None:
    """Sqorz-only mode's Next/Previous doesn't route through
    CurrentLineup.available_phases at all (that's a RaceManager-mode
    concept driven by RaceProgramService) -- must never imply RaceManager
    phase-stepping is available here."""
    slot = SqorzRaceSlot(
        class_code="C1", class_name="Test", phase_code="M1", phase_name="Moto 1", has_recorded_time=False
    )
    assert build_sqorz_only_lineup([], slot).available_phases == []


def test_lineup_with_no_riders_in_the_slot_is_a_valid_empty_lineup() -> None:
    slot = SqorzRaceSlot(
        class_code="C1", class_name="Empty Class", phase_code="M1", phase_name="Moto 1", has_recorded_time=False
    )
    lineup = build_sqorz_only_lineup([], slot)
    assert lineup.riders == []
    assert lineup.class_name == "Empty Class"


# ---------------------------------------------------------------------------
# empty_sqorz_only_lineup -- nothing selected yet
# ---------------------------------------------------------------------------


def test_empty_lineup_has_no_riders_and_a_plain_language_warning() -> None:
    lineup = empty_sqorz_only_lineup()
    assert lineup.riders == []
    assert lineup.warning
    assert lineup.source == "sqorz"


def test_empty_lineup_is_a_valid_current_lineup_not_a_special_case_downstream() -> None:
    """The overlay must be able to render this exactly like any other
    CurrentLineup -- construction succeeding at all is the assertion."""
    lineup = empty_sqorz_only_lineup()
    assert lineup.riders == []
    assert isinstance(lineup.class_name, str)
