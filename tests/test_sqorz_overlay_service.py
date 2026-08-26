"""The standalone Sqorz-only overlay's race selection -- no RaceManager involved."""

from __future__ import annotations

import json
from pathlib import Path

from connector.services.sqorz_overlay_service import build_overlay_state, build_race
from connector.services.sqorz_service import SqorzRiderTime, SqorzService

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def load_event_fixture() -> dict:
    return json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))


def row(
    *,
    class_name: str,
    phase_code: str = "M1",
    phase_name: str = "Moto 1",
    plate: str = "1",
    first_name: str = "A",
    last_name: str = "B",
    time_seconds: float | None = 40.0,
    result: int | None = None,
    class_timestamp: str | None = None,
    class_rank_phase_code: str | None = None,
) -> SqorzRiderTime:
    return SqorzRiderTime(
        class_code="C",
        class_name=class_name,
        plate=plate,
        first_name=first_name,
        last_name=last_name,
        transponder=None,
        phase_code=phase_code,
        phase_name=phase_name,
        time_seconds=time_seconds,
        time_raw=str(time_seconds) if time_seconds is not None else None,
        race_position=None,
        rank=None,
        result=result,
        class_timestamp=class_timestamp,
        class_rank_phase_code=class_rank_phase_code,
    )


# ---------------------------------------------------------------------------
# build_race: explicit selection, defaulting, sorting, blanks
# ---------------------------------------------------------------------------


def test_no_data_returns_no_race() -> None:
    assert build_race([], class_name=None, phase_code=None) is None


def test_explicit_class_and_phase_selects_exactly_that_race() -> None:
    rows = [
        row(class_name="7 Intermediate", phase_code="M1", last_name="Archer"),
        row(class_name="8 Novice", phase_code="M1", last_name="Vale"),
    ]
    race = build_race(rows, class_name="7 Intermediate", phase_code="M1")
    assert race is not None
    assert race.class_name == "7 Intermediate"
    assert [r.last_name for r in race.riders] == ["Archer"]


def test_unmatched_explicit_selection_returns_no_race() -> None:
    rows = [row(class_name="7 Intermediate", phase_code="M1")]
    assert build_race(rows, class_name="Does Not Exist", phase_code="M1") is None
    assert build_race(rows, class_name="7 Intermediate", phase_code="M9") is None


def test_riders_sort_fastest_first_then_untimed_last() -> None:
    rows = [
        row(class_name="X", last_name="Slow", time_seconds=50.0),
        row(class_name="X", last_name="NoTime", time_seconds=None),
        row(class_name="X", last_name="Fast", time_seconds=40.0),
    ]
    race = build_race(rows, class_name="X", phase_code="M1")
    assert [r.last_name for r in race.riders] == ["Fast", "Slow", "NoTime"]


def test_blank_time_is_none_not_a_guess() -> None:
    rows = [row(class_name="X", time_seconds=None)]
    race = build_race(rows, class_name="X", phase_code="M1")
    assert race.riders[0].time_seconds is None


def test_finish_carries_through_a_plausible_result() -> None:
    rows = [row(class_name="X", result=2)]
    race = build_race(rows, class_name="X", phase_code="M1")
    assert race.riders[0].finish == 2


def test_finish_hides_an_implausible_status_code() -> None:
    rows = [row(class_name="X", result=100400)]
    race = build_race(rows, class_name="X", phase_code="M1")
    assert race.riders[0].finish is None


def test_finish_never_affects_the_fastest_first_sort_order() -> None:
    """A slower rider can easily have a better cumulative finish across
    other phases -- this overlay sorts by this phase's time, full stop."""
    rows = [
        row(class_name="X", last_name="Slow", time_seconds=50.0, result=1),
        row(class_name="X", last_name="Fast", time_seconds=40.0, result=4),
    ]
    race = build_race(rows, class_name="X", phase_code="M1")
    assert [r.last_name for r in race.riders] == ["Fast", "Slow"]


def test_sqorz_phase_name_is_carried_through_deliberately() -> None:
    """Unlike the lineup overlay, this overlay is allowed to show Sqorz's
    own phase wording -- there is no BBS phase_label to protect here."""
    rows = [row(class_name="X", phase_code="1F", phase_name="Main")]
    race = build_race(rows, class_name="X", phase_code="1F")
    assert race.phase_name == "Main"


# ---------------------------------------------------------------------------
# Default selection heuristic: most recently updated class, its rankPhaseCode
# ---------------------------------------------------------------------------


def test_default_picks_the_most_recently_timestamped_class() -> None:
    rows = [
        row(
            class_name="Older Class",
            phase_code="M1",
            class_timestamp="2026-08-21T10:00:00.000Z",
            class_rank_phase_code="M1",
        ),
        row(
            class_name="Newer Class",
            phase_code="1F",
            class_timestamp="2026-08-21T18:00:00.000Z",
            class_rank_phase_code="1F",
        ),
    ]
    race = build_race(rows, class_name=None, phase_code=None)
    assert race.class_name == "Newer Class"
    assert race.phase_code == "1F"


def test_default_falls_back_to_first_race_when_no_class_has_a_timestamp() -> None:
    rows = [row(class_name="Only Class", phase_code="M2")]
    race = build_race(rows, class_name=None, phase_code=None)
    assert race.class_name == "Only Class"
    assert race.phase_code == "M2"


def test_default_class_with_explicit_phase_override() -> None:
    rows = [
        row(
            class_name="Newest",
            phase_code="M1",
            class_timestamp="2026-08-21T18:00:00.000Z",
            class_rank_phase_code="1F",
        ),
        row(class_name="Newest", phase_code="M2", class_timestamp="2026-08-21T18:00:00.000Z"),
    ]
    race = build_race(rows, class_name=None, phase_code="M2")
    assert race.class_name == "Newest"
    assert race.phase_code == "M2"


def test_default_heuristic_against_the_real_fixture_picks_a_real_class() -> None:
    from connector.services.sqorz_service import parse_event_payload

    rows = parse_event_payload(load_event_fixture())
    race = build_race(rows, class_name=None, phase_code=None)
    assert race is not None
    assert race.class_name
    assert race.riders


# ---------------------------------------------------------------------------
# build_overlay_state: disabled / unreachable / stale, never raises
# ---------------------------------------------------------------------------


def test_disabled_sqorz_returns_disabled_state_with_no_race() -> None:
    state = build_overlay_state(SqorzService(enabled=False), class_name=None, phase_code=None)
    assert state.enabled is False
    assert state.race is None


def test_unreachable_sqorz_returns_enabled_but_no_race() -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="nope")

    def boom(url: str) -> dict:
        raise OSError("down")

    sqorz._get_json = boom
    state = build_overlay_state(sqorz, class_name=None, phase_code=None)
    assert state.enabled is True
    assert state.reachable is False
    assert state.race is None
    assert state.error


def test_good_fetch_produces_a_race() -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="ok")
    sqorz._get_json = lambda url: load_event_fixture()
    state = build_overlay_state(sqorz, class_name=None, phase_code=None)
    assert state.enabled is True
    assert state.reachable is True
    assert state.race is not None
    assert state.race.riders
