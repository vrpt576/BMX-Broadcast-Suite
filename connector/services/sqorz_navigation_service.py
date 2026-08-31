"""Navigation over Sqorz's own rider-time data, for Sqorz-only mode.

There is no RaceManager here at all -- this module only ever consumes
list[SqorzRiderTime] (already fetched and parsed by SqorzService) and, in
LAN mode, SqorzService.last_phase_summaries_order. It never imports
database.racemanager, connector.dependencies' RaceManager-backed getters, or
any *_service.py that touches RaceManagerDatabase. See
docs/sqorz-only-mode.md for why that isolation matters and
test_sqorz_only_mode_never_touches_racemanager in
tests/test_sqorz_only_mode.py for the test that proves it end to end.

Two genuinely different navigation models, per the approved design (not one
model with a LAN/internet flag threaded through it):

  LAN mode has a real, Sqorz-documented running-order source
  (getPhaseSummaries -- see parse_lan_phase_summaries_order in
  sqorz_service.py) covering every class in the event, so a full-event
  catalog and Next/Previous across the whole thing is defensible. When that
  source doesn't cover a given (class, phase) pair -- including when it
  returned nothing this poll at all -- this falls back to a deterministic
  ordering (alphabetical by class name, canonical phase order within a
  class) for just the uncovered pairs, appended after the verified ones, so
  the catalog is always complete even when the primary source is only
  partially trustworthy this poll.

  Internet and file mode have NO ordering source at all -- Sqorz's own
  per-class timestamp is identical across every class in one payload (see
  sqorz_overlay_service.py's _default_class_and_phase, which hit this same
  wall first), so there is nothing to invent a cross-class running order
  from. Building one anyway would be a guess wearing the shape of a fact.
  Instead: a class picker (build_class_catalog), Next/Previous stepping
  through phases within whichever class is selected
  (build_class_phase_sequence), and a "jump to most recent activity" action
  scoped to that one class (find_most_recent_activity) rather than
  comparing timestamps across classes.

Both models share one stepping primitive (step()) -- a full-event LAN
catalog and a single class's phase sequence are both just "an ordered list
of slots"; exact-inverses is proven once, generically, against either.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from connector.services.sqorz_service import SqorzRiderTime

# M1/M2/M3 mirror the qualifying-round vocabulary
# sqorz_matching.ROUND_PHASE_TO_SQORZ_CODE maps RaceManager phases onto
# (duplicated here, not imported, so this module has zero dependency on
# anything that reasons about RaceManager rounds). "2F"/"1F" come from a
# real captured payload (tests/fixtures/sqorz/hoosier_day3_event.json,
# class 308 "12 Expert"): Sqorz's own phaseName for "2F" is "Semi Final"
# and for "1F" is "Main" -- confirming 2F runs before 1F, the reverse of
# what sorting the two purely alphabetically/numerically would produce. A
# code outside this table is never dropped, just sorted after every
# recognised one (in whatever order it was first encountered), so an event
# using a phase vocabulary this table doesn't yet know about still gets a
# complete, stable sequence -- degraded ordering, not degraded data.
_CANONICAL_PHASE_ORDER = {"M1": 0, "M2": 1, "M3": 2, "2F": 3, "1F": 4}


def _phase_sort_key(phase_code: str | None) -> tuple[int, str]:
    return (_CANONICAL_PHASE_ORDER.get(phase_code or "", len(_CANONICAL_PHASE_ORDER)), phase_code or "")


@dataclass(frozen=True)
class SqorzRaceSlot:
    """One navigable race: a (class, phase) pair, not an individual rider.

    phase_name is Sqorz's own name for this phase (e.g. "Moto 1", "Main") --
    in Sqorz-only mode this IS the round label, since there is no
    RaceManager finalization method to defer to (contrast with mixed mode,
    where current_lineup_service._augment_with_sqorz never touches
    phase_label at all -- see docs/racemanager-round-model.md). Whichever
    module turns a SqorzRaceSlot into a displayed round label must read it
    from here, never invent one.
    """

    class_code: str | None
    class_name: str | None
    phase_code: str | None
    phase_name: str | None
    has_recorded_time: bool
    # True only when this slot's position in the catalog came from a
    # verified ordering source (LAN's getPhaseSummaries); False when it was
    # placed by the deterministic fallback. Surfaced so a caller (the
    # Director UI, a test) can tell "Sqorz told us this order" apart from
    # "we guessed a reasonable order" without re-deriving it.
    ordered_by_sqorz: bool = False


def slot_key(slot: SqorzRaceSlot) -> tuple[str | None, str | None]:
    return (slot.class_code, slot.phase_code)


def _group_by_slot(riders: Sequence[SqorzRiderTime]) -> dict[tuple[str | None, str | None], list[SqorzRiderTime]]:
    groups: dict[tuple[str | None, str | None], list[SqorzRiderTime]] = {}
    for rider in riders:
        groups.setdefault((rider.class_code, rider.phase_code), []).append(rider)
    return groups


def _slot_from_group(key: tuple[str | None, str | None], rows: list[SqorzRiderTime], *, ordered_by_sqorz: bool) -> SqorzRaceSlot:
    class_code, phase_code = key
    class_name = next((row.class_name for row in rows if row.class_name), None)
    phase_name = next((row.phase_name for row in rows if row.phase_name), None)
    has_recorded_time = any(row.time_seconds is not None for row in rows)
    return SqorzRaceSlot(
        class_code=class_code,
        class_name=class_name,
        phase_code=phase_code,
        phase_name=phase_name,
        has_recorded_time=has_recorded_time,
        ordered_by_sqorz=ordered_by_sqorz,
    )


# ---------------------------------------------------------------------------
# Internet / file mode: class picker + within-class phase stepping.
# No cross-class ordering exists here -- see the module docstring.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SqorzClassSummary:
    class_code: str | None
    class_name: str | None


def build_class_catalog(riders: Sequence[SqorzRiderTime]) -> list[SqorzClassSummary]:
    """Every distinct class present in the current payload, alphabetised by
    name -- a plain picker list, not a claim about running order. Sorting
    alphabetically (rather than, say, payload order) is a deliberate,
    inert choice: it makes the picker predictable without implying anything
    about which class races next, which is exactly the claim this mode
    cannot make (see module docstring)."""
    seen: dict[tuple[str | None, str | None], None] = {}
    for rider in riders:
        seen.setdefault((rider.class_code, rider.class_name), None)
    return sorted(
        (SqorzClassSummary(class_code=code, class_name=name) for code, name in seen),
        key=lambda summary: (summary.class_name or "").lower(),
    )


def build_class_phase_sequence(riders: Sequence[SqorzRiderTime], class_code: str | None) -> list[SqorzRaceSlot]:
    """Every phase recorded for one class, in canonical M1 < M2 < M3 < 1F
    order (recognised codes), with anything outside that vocabulary appended
    afterward in first-seen order -- never a cross-class claim, and never
    inventing a phase that isn't actually present in the data."""
    grouped = _group_by_slot(rider for rider in riders if rider.class_code == class_code)
    slots = [_slot_from_group(key, rows, ordered_by_sqorz=False) for key, rows in grouped.items()]
    return sorted(slots, key=lambda slot: _phase_sort_key(slot.phase_code))


def find_most_recent_activity(riders: Sequence[SqorzRiderTime], class_code: str | None) -> SqorzRaceSlot | None:
    """The furthest-along phase in this class that has at least one recorded
    time -- "jump to where scoring actually is" for the selected class,
    without comparing anything across classes (see module docstring for why
    that comparison isn't available). Falls back to the first phase in the
    sequence when nothing has a time yet -- nothing has started, so "most
    recent" is trivially "the beginning"."""
    sequence = build_class_phase_sequence(riders, class_code)
    if not sequence:
        return None
    with_time = [slot for slot in sequence if slot.has_recorded_time]
    return with_time[-1] if with_time else sequence[0]


# ---------------------------------------------------------------------------
# LAN mode: a full-event catalog, ordered primarily by getPhaseSummaries.
# ---------------------------------------------------------------------------


def build_lan_catalog(
    riders: Sequence[SqorzRiderTime],
    phase_summaries_order: Sequence[tuple[str | None, str | None]],
) -> list[SqorzRaceSlot]:
    """Every (class, phase) pair actually present in the polled rider data,
    ordered primarily by phase_summaries_order (SqorzService's parsed guess
    at getPhaseSummaries's running order) -- pairs that source doesn't cover
    (including every pair, when it returned nothing this poll) fall back to
    a deterministic order (alphabetical class name, canonical phase) and are
    appended after the verified ones, each flagged ordered_by_sqorz=False so
    a caller can tell the two apart."""
    grouped = _group_by_slot(riders)
    position = {key: index for index, key in enumerate(phase_summaries_order)}

    verified: list[SqorzRaceSlot] = []
    fallback: list[SqorzRaceSlot] = []
    for key, rows in grouped.items():
        if key in position:
            verified.append(_slot_from_group(key, rows, ordered_by_sqorz=True))
        else:
            fallback.append(_slot_from_group(key, rows, ordered_by_sqorz=False))

    verified.sort(key=lambda slot: position[slot_key(slot)])
    fallback.sort(key=lambda slot: ((slot.class_name or "").lower(), _phase_sort_key(slot.phase_code)))
    return verified + fallback


# ---------------------------------------------------------------------------
# Shared stepping primitive -- proves exact-inverses once, for either scope.
# ---------------------------------------------------------------------------


def step(
    catalog: Sequence[SqorzRaceSlot],
    current_key: tuple[str | None, str | None] | None,
    direction: int,
) -> SqorzRaceSlot | None:
    """Move exactly one slot forward or back through catalog. Clamps at
    either end -- stepping past the last or before the first slot is a
    no-op, mirroring RaceProgramService.step_moto's own clamped-not-wrapped
    convention (connector/services/race_program_service.py), which is also
    exactly what makes step(+1) followed by step(-1) an exact inverse: a
    clamped no-op's own inverse is itself.

    Returns None only when the catalog is empty. When current_key isn't
    found in the catalog at all (e.g. the previously-selected slot dropped
    out of this poll's data), starts from just outside whichever end
    direction moves toward, so the first step lands on the first (or last)
    slot rather than silently going nowhere.
    """
    if not catalog:
        return None
    index = next((i for i, slot in enumerate(catalog) if slot_key(slot) == current_key), None)
    if direction == 0:
        return catalog[index] if index is not None else catalog[0]

    step_by = 1 if direction > 0 else -1
    if index is None:
        return catalog[0] if step_by > 0 else catalog[-1]
    target = index + step_by
    if not 0 <= target < len(catalog):
        return catalog[index]  # clamped: stepping past either end is a no-op
    return catalog[target]
