"""Navigation over Sqorz-only rider data -- tested hard against a real
captured internet-mode payload (tests/fixtures/sqorz/hoosier_day3_event.json)
before anything gets built on top of it, per the approved 1.3.2 design.
Real data caught a real bug: class 308 "12 Expert" has a "2F" (Semi Final)
phase the original canonical-order table didn't recognise, which would have
sorted it after "1F" (Main) -- backwards. See sqorz_navigation_service.py's
module docstring and _CANONICAL_PHASE_ORDER comment for the fix.

LAN-mode catalog building (build_lan_catalog) has no real payload to test
against -- getPhaseSummaries has never been captured on site (see
parse_lan_phase_summaries_order in sqorz_service.py) -- so those tests use
synthetic (class_code, phase_code) tuples, clearly labelled as such, and
only assert the merge/fallback/ordered_by_sqorz logic, never a claim about
what Sqorz actually sends.
"""

from __future__ import annotations

import json
from pathlib import Path

from connector.services.sqorz_navigation_service import (
    build_class_catalog,
    build_class_phase_sequence,
    build_lan_catalog,
    find_most_recent_activity,
    slot_key,
    step,
)
from connector.services.sqorz_service import SqorzRiderTime, parse_event_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def load_real_riders() -> list[SqorzRiderTime]:
    payload = json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))
    return parse_event_payload(payload)


def rider(
    *,
    class_code: str | None = "C1",
    class_name: str | None = "Test Class",
    phase_code: str | None = "M1",
    phase_name: str | None = "Moto 1",
    time_seconds: float | None = None,
    plate: str | None = "1",
    last_name: str | None = "RIDER",
) -> SqorzRiderTime:
    return SqorzRiderTime(
        class_code=class_code,
        class_name=class_name,
        plate=plate,
        first_name="A",
        last_name=last_name,
        transponder=None,
        phase_code=phase_code,
        phase_name=phase_name,
        time_seconds=time_seconds,
        time_raw=None,
        race_position=None,
        rank=None,
    )


# ---------------------------------------------------------------------------
# build_class_catalog -- real data
# ---------------------------------------------------------------------------


def test_class_catalog_lists_every_real_class_alphabetically() -> None:
    catalog = build_class_catalog(load_real_riders())
    names = [c.class_name for c in catalog]
    assert names == sorted(names, key=str.lower)
    assert "12 Expert" in names
    assert "11-12 Open" in names


def test_class_catalog_has_no_duplicates() -> None:
    catalog = build_class_catalog(load_real_riders())
    codes = [c.class_code for c in catalog]
    assert len(codes) == len(set(codes))


def test_class_catalog_empty_riders_is_empty_not_an_error() -> None:
    assert build_class_catalog([]) == []


# ---------------------------------------------------------------------------
# build_class_phase_sequence -- real data, including the 2F/1F ordering fix
# ---------------------------------------------------------------------------


def test_phase_sequence_for_the_class_with_a_semi_final_orders_2f_before_1f() -> None:
    """The concrete bug real data caught: 12 Expert (classCode 308) runs
    M1, M2, then a Semi Final (2F) before the Main (1F) -- confirmed by
    Sqorz's own phaseName strings in the fixture, not assumed."""
    riders = load_real_riders()
    sequence = build_class_phase_sequence(riders, "308")
    codes = [slot.phase_code for slot in sequence]
    assert codes == ["M1", "M2", "2F", "1F"]
    names = dict(zip(codes, [slot.phase_name for slot in sequence]))
    assert names["2F"] == "Semi Final"
    assert names["1F"] == "Main"


def test_phase_sequence_for_a_three_moto_class_is_m1_m2_m3() -> None:
    riders = load_real_riders()
    sequence = build_class_phase_sequence(riders, "2206")  # "15-16 Open"
    assert [slot.phase_code for slot in sequence] == ["M1", "M2", "M3"]


def test_phase_sequence_for_unknown_class_code_is_empty() -> None:
    assert build_class_phase_sequence(load_real_riders(), "not-a-real-class") == []


def test_phase_sequence_never_marks_any_slot_as_sqorz_ordered() -> None:
    """Internet/file mode has no ordering source at all (see module
    docstring) -- every slot here must be flagged as the deterministic
    fallback, never as verified."""
    sequence = build_class_phase_sequence(load_real_riders(), "308")
    assert all(slot.ordered_by_sqorz is False for slot in sequence)


def test_unrecognised_phase_code_sorts_after_the_known_vocabulary() -> None:
    riders = [
        rider(phase_code="M1", phase_name="Moto 1"),
        rider(phase_code="WEIRD", phase_name="Something New"),
        rider(phase_code="1F", phase_name="Main"),
    ]
    sequence = build_class_phase_sequence(riders, "C1")
    assert [slot.phase_code for slot in sequence] == ["M1", "1F", "WEIRD"]


# ---------------------------------------------------------------------------
# find_most_recent_activity
# ---------------------------------------------------------------------------


def test_most_recent_activity_is_the_furthest_phase_with_a_recorded_time() -> None:
    riders = load_real_riders()
    slot = find_most_recent_activity(riders, "308")
    assert slot is not None
    assert slot.phase_code == "1F"  # every 1F row in the fixture has a real time


def test_most_recent_activity_falls_back_to_the_first_phase_when_nothing_has_started() -> None:
    riders = [rider(phase_code="M1", time_seconds=None), rider(phase_code="M2", time_seconds=None)]
    slot = find_most_recent_activity(riders, "C1")
    assert slot is not None
    assert slot.phase_code == "M1"


def test_most_recent_activity_skips_a_later_phase_with_no_times_yet() -> None:
    """M2 exists (riders are entered) but nobody has run it yet -- activity
    is still "at" M1, not M2, since a time is what "activity" means here."""
    riders = [
        rider(phase_code="M1", time_seconds=41.0, plate="1"),
        rider(phase_code="M2", time_seconds=None, plate="1"),
    ]
    slot = find_most_recent_activity(riders, "C1")
    assert slot.phase_code == "M1"


def test_most_recent_activity_for_unknown_class_is_none() -> None:
    assert find_most_recent_activity(load_real_riders(), "not-a-real-class") is None


# ---------------------------------------------------------------------------
# step() -- the shared primitive; exact-inverses proven generically, reused
# by both scopes (a real class's phase sequence here; a synthetic LAN
# catalog below)
# ---------------------------------------------------------------------------


def test_step_forward_then_backward_through_a_real_class_returns_to_start() -> None:
    sequence = build_class_phase_sequence(load_real_riders(), "308")
    start_key = slot_key(sequence[0])

    forward = step(sequence, start_key, +1)
    back = step(sequence, slot_key(forward), -1)

    assert slot_key(back) == start_key


def test_step_walks_the_full_sequence_in_order() -> None:
    sequence = build_class_phase_sequence(load_real_riders(), "308")
    codes = [sequence[0].phase_code]
    current = slot_key(sequence[0])
    for _ in range(len(sequence) - 1):
        nxt = step(sequence, current, +1)
        codes.append(nxt.phase_code)
        current = slot_key(nxt)
    assert codes == ["M1", "M2", "2F", "1F"]


def test_step_forward_clamps_at_the_last_slot() -> None:
    sequence = build_class_phase_sequence(load_real_riders(), "308")
    last_key = slot_key(sequence[-1])
    assert slot_key(step(sequence, last_key, +1)) == last_key


def test_step_backward_clamps_at_the_first_slot() -> None:
    sequence = build_class_phase_sequence(load_real_riders(), "308")
    first_key = slot_key(sequence[0])
    assert slot_key(step(sequence, first_key, -1)) == first_key


def test_step_from_an_unknown_key_lands_on_the_first_slot_moving_forward() -> None:
    sequence = build_class_phase_sequence(load_real_riders(), "308")
    result = step(sequence, ("nonexistent", "nowhere"), +1)
    assert slot_key(result) == slot_key(sequence[0])


def test_step_from_an_unknown_key_lands_on_the_last_slot_moving_backward() -> None:
    sequence = build_class_phase_sequence(load_real_riders(), "308")
    result = step(sequence, ("nonexistent", "nowhere"), -1)
    assert slot_key(result) == slot_key(sequence[-1])


def test_step_on_an_empty_catalog_returns_none() -> None:
    assert step([], None, +1) is None


# ---------------------------------------------------------------------------
# build_lan_catalog -- SYNTHETIC data only; no real getPhaseSummaries
# payload has ever been captured. Tests the merge/fallback/ordering-flag
# logic, not a claim about Sqorz's real shape.
# ---------------------------------------------------------------------------


def test_lan_catalog_orders_by_the_verified_source_when_it_covers_everything() -> None:
    riders = [
        rider(class_code="C1", class_name="Alpha", phase_code="M1"),
        rider(class_code="C2", class_name="Beta", phase_code="M1"),
    ]
    order = [("C2", "M1"), ("C1", "M1")]  # deliberately not alphabetical

    catalog = build_lan_catalog(riders, order)

    assert [(slot.class_code, slot.phase_code) for slot in catalog] == [("C2", "M1"), ("C1", "M1")]
    assert all(slot.ordered_by_sqorz for slot in catalog)


def test_lan_catalog_falls_back_deterministically_when_the_source_is_empty() -> None:
    """No verified ordering this poll (getPhaseSummaries failed or didn't
    match) -- falls back to alphabetical class / canonical phase, same
    deterministic rule internet/file mode always uses, rather than
    reproducing whatever order the rider rows happened to arrive in."""
    riders = [
        rider(class_code="C2", class_name="Beta", phase_code="M1"),
        rider(class_code="C1", class_name="Alpha", phase_code="M2"),
        rider(class_code="C1", class_name="Alpha", phase_code="M1"),
    ]
    catalog = build_lan_catalog(riders, [])
    assert [(slot.class_code, slot.phase_code) for slot in catalog] == [
        ("C1", "M1"),
        ("C1", "M2"),
        ("C2", "M1"),
    ]
    assert all(slot.ordered_by_sqorz is False for slot in catalog)


def test_lan_catalog_mixes_verified_and_fallback_pairs_correctly() -> None:
    """A pair the ordering source doesn't cover is appended after every
    verified pair, not interleaved -- verified entries keep the source's
    order among themselves regardless of what's appended after."""
    riders = [
        rider(class_code="C1", class_name="Alpha", phase_code="M1"),
        rider(class_code="C2", class_name="Beta", phase_code="M1"),  # not in order
    ]
    order = [("C1", "M1")]

    catalog = build_lan_catalog(riders, order)

    assert [(slot.class_code, slot.phase_code) for slot in catalog] == [
        ("C1", "M1"),
        ("C2", "M1"),
    ]
    assert catalog[0].ordered_by_sqorz is True
    assert catalog[1].ordered_by_sqorz is False


def test_lan_catalog_ignores_order_entries_with_no_matching_rider_data() -> None:
    """getPhaseSummaries can only ever add ordering for races BBS actually
    has rider data for -- an entry naming a (class, phase) pair nobody has
    raced yet must not fabricate a slot with no riders."""
    riders = [rider(class_code="C1", class_name="Alpha", phase_code="M1")]
    order = [("C1", "M1"), ("C1", "M2")]  # M2 not in riders at all

    catalog = build_lan_catalog(riders, order)

    assert len(catalog) == 1
    assert catalog[0].phase_code == "M1"


def test_step_exact_inverses_across_a_synthetic_lan_catalog() -> None:
    riders = [
        rider(class_code="C1", class_name="Alpha", phase_code="M1"),
        rider(class_code="C1", class_name="Alpha", phase_code="M2"),
        rider(class_code="C2", class_name="Beta", phase_code="M1"),
    ]
    order = [("C1", "M1"), ("C2", "M1"), ("C1", "M2")]
    catalog = build_lan_catalog(riders, order)

    mid_key = slot_key(catalog[1])
    forward = step(catalog, mid_key, +1)
    back = step(catalog, slot_key(forward), -1)
    assert slot_key(back) == mid_key


# ---------------------------------------------------------------------------
# SqorzRaceSlot construction sanity -- has_recorded_time and phase_name are
# read straight from the underlying rider rows, not recomputed elsewhere
# ---------------------------------------------------------------------------


def test_slot_has_recorded_time_true_when_any_rider_has_a_time() -> None:
    riders = [
        rider(phase_code="M1", time_seconds=None, plate="1"),
        rider(phase_code="M1", time_seconds=42.0, plate="2"),
    ]
    sequence = build_class_phase_sequence(riders, "C1")
    assert sequence[0].has_recorded_time is True


def test_slot_has_recorded_time_false_when_no_rider_has_a_time() -> None:
    riders = [rider(phase_code="M1", time_seconds=None)]
    sequence = build_class_phase_sequence(riders, "C1")
    assert sequence[0].has_recorded_time is False
