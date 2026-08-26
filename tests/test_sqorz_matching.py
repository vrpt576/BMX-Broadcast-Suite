"""Matching confidence tiers -- only exact/strong ever produce a displayed time."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from connector.models import RacePhase
from connector.services.sqorz_matching import (
    ROUND_PHASE_TO_SQORZ_CODE,
    MatchConfidence,
    match_class,
    time_for_phase,
)
from connector.services.sqorz_service import SqorzRiderTime, parse_event_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def load_event_fixture() -> dict:
    return json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))


@dataclass
class FakeRider:
    bike_number: str | int | None
    first_name: str
    last_name: str


def sqorz_row(
    *,
    plate: str,
    first_name: str,
    last_name: str,
    class_name: str = "7 Intermediate",
    phase_code: str = "M1",
    time_seconds: float | None = 40.0,
) -> SqorzRiderTime:
    return SqorzRiderTime(
        class_code="C1",
        class_name=class_name,
        plate=plate,
        first_name=first_name,
        last_name=last_name,
        transponder=None,
        phase_code=phase_code,
        phase_name="Moto 1",
        time_seconds=time_seconds,
        time_raw=str(time_seconds) if time_seconds is not None else None,
        race_position=None,
        rank=None,
    )


# ---------------------------------------------------------------------------
# Round -> Sqorz phaseCode mapping
# ---------------------------------------------------------------------------


def test_round_to_sqorz_phase_code_mapping() -> None:
    assert ROUND_PHASE_TO_SQORZ_CODE[RacePhase.ROUND_1] == "M1"
    assert ROUND_PHASE_TO_SQORZ_CODE[RacePhase.ROUND_2] == "M2"
    assert ROUND_PHASE_TO_SQORZ_CODE[RacePhase.ROUND_3] == "M3"
    assert ROUND_PHASE_TO_SQORZ_CODE[RacePhase.MAIN] == "1F"
    assert RacePhase.QUARTERFINAL not in ROUND_PHASE_TO_SQORZ_CODE
    assert RacePhase.SEMIFINAL not in ROUND_PHASE_TO_SQORZ_CODE


# ---------------------------------------------------------------------------
# Confidence tiers
# ---------------------------------------------------------------------------


def test_exact_match_plate_and_last_name_produces_a_time() -> None:
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")
    rows = [sqorz_row(plate="17", first_name="NOVA", last_name="ARCHER", time_seconds=41.2)]

    matches, report = match_class([rider], "7 Intermediate", rows)

    assert matches[0].confidence == MatchConfidence.EXACT
    assert time_for_phase(matches[0], "M1") == 41.2
    assert report.counts["exact"] == 1
    assert report.unmatched_bbs == []


def test_strong_match_requires_the_same_resolved_class() -> None:
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")
    # Same plate, different last name -- can't be "exact" -- but same class,
    # so plate alone is trusted as "strong".
    rows = [sqorz_row(plate="17", first_name="Someone", last_name="Else", time_seconds=41.2)]

    matches, report = match_class([rider], "7 Intermediate", rows)

    assert matches[0].confidence == MatchConfidence.STRONG
    assert time_for_phase(matches[0], "M1") == 41.2


def test_a_plate_only_whole_event_fallback_match_never_reaches_strong() -> None:
    """CONFIRMED against a real 829-rider national field during the dress
    rehearsal: when class names don't line up, plate-only-across-the-whole-
    event WILL collide by chance. A bare plate match there is capped at
    "weak" (recorded, never displayed) -- "strong" requires the safety of a
    genuinely class-scoped pool. See sqorz_matching.py's comment."""
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")
    rows = [sqorz_row(plate="17", first_name="Someone", last_name="Else", class_name="8 Novice")]

    matches, report = match_class([rider], "7 Intermediate", rows)

    assert report.class_match_path == "plate_only"
    assert matches[0].confidence == MatchConfidence.WEAK
    assert time_for_phase(matches[0], "M1") is None


def test_a_plate_match_within_the_real_resolved_class_stays_strong() -> None:
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")
    rows = [
        sqorz_row(plate="17", first_name="Someone", last_name="Else", class_name="7 Intermediate"),
        sqorz_row(plate="4", first_name="Other", last_name="Rider", class_name="8 Novice"),
    ]

    matches, report = match_class([rider], "7 Intermediate", rows)

    assert report.class_match_path == "class_name"
    assert matches[0].confidence == MatchConfidence.STRONG


def test_weak_match_never_produces_a_displayed_time() -> None:
    rider = FakeRider(bike_number=99, first_name="Nova", last_name="Archer")
    # Different plate, but name matches within the class -- "weak".
    rows = [sqorz_row(plate="5", first_name="Nova", last_name="Archer", time_seconds=41.2)]

    matches, report = match_class([rider], "7 Intermediate", rows)

    assert matches[0].confidence == MatchConfidence.WEAK
    assert time_for_phase(matches[0], "M1") is None  # never displayed
    assert report.counts["weak"] == 1


def test_no_match_produces_none_and_is_recorded_as_unmatched() -> None:
    rider = FakeRider(bike_number=99, first_name="Zed", last_name="Zephyr")
    rows = [sqorz_row(plate="5", first_name="Nova", last_name="Archer")]

    matches, report = match_class([rider], "7 Intermediate", rows)

    assert matches[0].confidence == MatchConfidence.NONE
    assert time_for_phase(matches[0], "M1") is None
    assert "Zed Zephyr" in report.unmatched_bbs
    assert "Nova Archer" in report.unmatched_sqorz


def test_exact_beats_strong_when_both_are_possible() -> None:
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")
    rows = [
        sqorz_row(plate="17", first_name="Someone", last_name="Else", time_seconds=99.0),
        sqorz_row(plate="4", first_name="Nova", last_name="Archer", time_seconds=41.2),
    ]
    # Neither row alone is exact; add the true exact match too.
    rows.append(sqorz_row(plate="17", first_name="Nova", last_name="Archer", time_seconds=40.0))

    matches, _report = match_class([rider], "7 Intermediate", rows)

    assert matches[0].confidence == MatchConfidence.EXACT
    assert time_for_phase(matches[0], "M1") == 40.0


def test_normalization_ignores_case_and_punctuation() -> None:
    rider = FakeRider(bike_number="17-A", first_name="Mary-Jane", last_name="O'Brien")
    rows = [sqorz_row(plate="17A", first_name="MARYJANE", last_name="OBRIEN", time_seconds=41.2)]

    matches, _report = match_class([rider], "7 Intermediate", rows)

    assert matches[0].confidence == MatchConfidence.EXACT


def test_missing_time_for_the_selected_phase_shows_blank_even_with_a_strong_match() -> None:
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")
    rows = [sqorz_row(plate="17", first_name="Nova", last_name="Archer", phase_code="M1", time_seconds=None)]

    matches, _report = match_class([rider], "7 Intermediate", rows)

    assert matches[0].confidence == MatchConfidence.EXACT
    assert time_for_phase(matches[0], "M1") is None


def test_time_for_phase_returns_none_for_a_phase_the_rider_has_no_row_for() -> None:
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")
    rows = [sqorz_row(plate="17", first_name="Nova", last_name="Archer", phase_code="M1")]

    matches, _report = match_class([rider], "7 Intermediate", rows)

    assert time_for_phase(matches[0], "1F") is None


def test_no_sqorz_data_leaves_every_rider_unmatched_without_raising() -> None:
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")

    matches, report = match_class([rider], "7 Intermediate", [])

    assert matches[0].confidence == MatchConfidence.NONE
    assert report.class_match_path == "no_sqorz_data"


# ---------------------------------------------------------------------------
# Plate is not unique -- real Dobelle/Hinderlider collision (plate 9,
# "11-12 Open", Hoosier - Day 3, confirmed live 2026-08-25).
# ---------------------------------------------------------------------------


def test_real_plate_collision_never_lets_a_bare_plate_reach_strong() -> None:
    rows = parse_event_payload(load_event_fixture())

    # An unrelated BBS rider on plate 9 must not receive either Dobelle's or
    # Hinderlider's time -- the plate alone cannot say which one is meant.
    stranger = FakeRider(bike_number=9, first_name="Someone", last_name="Else")
    matches, report = match_class([stranger], "11-12 Open", rows)

    assert matches[0].confidence != MatchConfidence.STRONG
    assert time_for_phase(matches[0], "M1") is None
    assert any(
        "#9" in note and "Dobelle".upper() in note.upper() and "Hinderlider".upper() in note.upper()
        for note in report.ambiguous_plates
    )


def test_real_plate_collision_still_resolves_by_exact_last_name_match() -> None:
    rows = parse_event_payload(load_event_fixture())

    dylan = FakeRider(bike_number=9, first_name="Dylan", last_name="Dobelle")
    wade = FakeRider(bike_number=9, first_name="Wade", last_name="Hinderlider")
    matches, _report = match_class([dylan, wade], "11-12 Open", rows)

    # Last name disambiguates a shared plate -- each rider gets their own,
    # correct time, never each other's.
    assert matches[0].confidence == MatchConfidence.EXACT
    assert matches[1].confidence == MatchConfidence.EXACT
    assert time_for_phase(matches[0], "M1") == 55.682  # Dobelle's real M1 time
    assert time_for_phase(matches[1], "M1") == 56.094  # Hinderlider's real M1 time


def test_ambiguous_sqorz_plate_falls_through_to_weak_by_name_when_available() -> None:
    """A stranger sharing the ambiguous plate but matching neither collider's
    name still can't reach "strong" -- and correctly reaches "none", not a
    guessed identity."""
    rows = parse_event_payload(load_event_fixture())
    stranger = FakeRider(bike_number=9, first_name="Nobody", last_name="Unrelated")

    matches, _report = match_class([stranger], "11-12 Open", rows)

    assert matches[0].confidence == MatchConfidence.NONE


def test_bbs_side_duplicate_bike_number_also_blocks_strong() -> None:
    """Two RaceManager riders sharing a bike number is exactly as unsafe as
    two Sqorz competitors sharing a plate -- gate both sides."""
    rider_a = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")
    rider_b = FakeRider(bike_number=17, first_name="Someone", last_name="Different")
    rows = [sqorz_row(plate="17", first_name="Third", last_name="Party", class_name="7 Intermediate")]

    matches, report = match_class([rider_a, rider_b], "7 Intermediate", rows)

    assert matches[0].confidence != MatchConfidence.STRONG
    assert matches[1].confidence != MatchConfidence.STRONG
    assert any("(RaceManager)" in note for note in report.ambiguous_plates)


def test_unique_plate_within_class_is_unaffected_by_the_ambiguity_gate() -> None:
    rows = parse_event_payload(load_event_fixture())
    rider = FakeRider(bike_number=20, first_name="Racyn", last_name="Murfin")

    matches, report = match_class([rider], "11-12 Open", rows)

    assert matches[0].confidence == MatchConfidence.EXACT
    assert not any("#20" in note for note in report.ambiguous_plates)


# ---------------------------------------------------------------------------
# Operator-set class aliases (see SqorzClassAliasStore)
# ---------------------------------------------------------------------------


def test_class_alias_finds_a_class_that_normalised_name_matching_would_miss() -> None:
    rows = parse_event_payload(load_event_fixture())
    # RaceManager calls it something Sqorz has no name-match for at all.
    rider = FakeRider(bike_number=20, first_name="Racyn", last_name="Murfin")

    without_alias, report_without = match_class(
        [rider], "RaceManager's Weird Class Name", rows
    )
    with_alias, report_with = match_class(
        [rider], "RaceManager's Weird Class Name", rows, class_alias="11-12 Open"
    )

    assert report_without.class_match_path == "plate_only"
    assert report_with.class_match_path == "alias"
    assert with_alias[0].confidence == MatchConfidence.EXACT
    assert time_for_phase(with_alias[0], "M1") == 47.529


def test_class_alias_matches_by_sqorz_class_code_too() -> None:
    rows = parse_event_payload(load_event_fixture())
    rider = FakeRider(bike_number=20, first_name="Racyn", last_name="Murfin")

    matches, report = match_class(
        [rider], "RaceManager's Weird Class Name", rows, class_alias="2204"
    )

    assert report.class_match_path == "alias"
    assert matches[0].confidence == MatchConfidence.EXACT


def test_an_alias_that_matches_nothing_falls_back_to_normal_resolution() -> None:
    rows = parse_event_payload(load_event_fixture())
    rider = FakeRider(bike_number=20, first_name="Racyn", last_name="Murfin")

    matches, report = match_class(
        [rider], "11-12 Open", rows, class_alias="Does Not Exist Anywhere"
    )

    # Bad alias didn't crash anything -- falls through to the class name,
    # which does resolve correctly here.
    assert report.class_match_path == "class_name"
    assert matches[0].confidence == MatchConfidence.EXACT


def test_no_alias_behaves_exactly_as_before() -> None:
    rows = [sqorz_row(plate="17", first_name="Nova", last_name="Archer", class_name="7 Intermediate")]
    rider = FakeRider(bike_number=17, first_name="Nova", last_name="Archer")

    matches, report = match_class([rider], "7 Intermediate", rows, class_alias=None)

    assert report.class_match_path == "class_name"
    assert matches[0].confidence == MatchConfidence.EXACT
