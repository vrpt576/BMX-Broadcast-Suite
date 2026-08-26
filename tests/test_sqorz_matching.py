"""Matching confidence tiers -- only exact/strong ever produce a displayed time."""

from __future__ import annotations

from dataclasses import dataclass

from connector.models import RacePhase
from connector.services.sqorz_matching import (
    ROUND_PHASE_TO_SQORZ_CODE,
    MatchConfidence,
    match_class,
    time_for_phase,
)
from connector.services.sqorz_service import SqorzRiderTime


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
