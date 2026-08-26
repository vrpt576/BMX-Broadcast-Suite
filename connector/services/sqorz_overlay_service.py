"""Build the standalone Sqorz-only overlay's current race -- no RaceManager.

This is the counterpart to sqorz_matching.py's lineup timing column, for the
opposite situation: no RaceManager available at all (e.g. Smith Rock has no
BBS-reachable RaceManager). This overlay reads ONLY the Sqorz feed -- it must
never touch MotoboardService, CurrentMotoService, the race slot catalog, or
any RaceManager query. That is the entire point: if RaceManager is
unconfigured or down, this overlay still works.

Sqorz's own phase names (e.g. "Moto 1", "Main") ARE displayed here -- this
overlay presents Sqorz's own view of the event, not BBS's RaceManager-derived
race program, so there is no phase_label/RaceStage.label to protect. Do not
later wire anything from this module into those (see CLAUDE.md and
sqorz_matching.py, which enforces the opposite rule for the lineup overlay).
"""

from __future__ import annotations

from connector.models import SqorzOverlayRace, SqorzOverlayRider, SqorzOverlayState
from connector.services.sqorz_service import SqorzRiderTime, SqorzService


def _default_class_and_phase(rows: list[SqorzRiderTime]) -> tuple[str | None, str | None]:
    """Simple heuristic: the class with the most recently updated Sqorz
    class-level timestamp, using that class's own rankPhaseCode as the
    phase to show (falling back to any phase code seen for that class).

    Deliberately simple -- meant to "do something sensible" with no query
    parameters, not to be clever.

    CONFIRMED against the live internet API (2026-08-25, Hoosier - Day 3):
    every classRank in one payload shares exactly one identical `timestamp`
    value -- it's a payload-generation time, not a per-class update time. In
    internet mode this heuristic therefore always resolves to whichever
    class happens to come first in `classRanks` order (ties never overwrite
    `best_*` below), not genuinely "most recent". It's still deterministic
    and shows a real race, which is the actual bar here. Whether the LAN
    API's getPhaseBlockSummaries carries a real per-block timestamp is
    unverified -- confirm with scripts/sqorz_probe.py and, if so, this
    heuristic becomes meaningful there without any code change (it already
    reads whatever value each backend supplies).
    """
    best_class_name: str | None = None
    best_phase: str | None = None
    best_timestamp = ""
    fallback_phase_by_class: dict[str, str] = {}

    for row in rows:
        if row.class_name and row.class_name not in fallback_phase_by_class:
            fallback_phase_by_class[row.class_name] = row.phase_code
        if row.class_timestamp and row.class_timestamp > best_timestamp:
            best_timestamp = row.class_timestamp
            best_class_name = row.class_name
            best_phase = row.class_rank_phase_code

    if best_class_name and not best_phase:
        best_phase = fallback_phase_by_class.get(best_class_name)
    if best_class_name is None and rows:
        # No class carried a timestamp at all (e.g. a hand-built LAN
        # payload) -- fall back to simply the first race seen.
        best_class_name = rows[0].class_name
        best_phase = rows[0].phase_code
    return best_class_name, best_phase


def build_race(
    rows: list[SqorzRiderTime],
    *,
    class_name: str | None,
    phase_code: str | None,
) -> SqorzOverlayRace | None:
    if not rows:
        return None
    if not class_name or not phase_code:
        default_class, default_phase = _default_class_and_phase(rows)
        class_name = class_name or default_class
        phase_code = phase_code or default_phase
    if not class_name or not phase_code:
        return None

    matching = [
        row for row in rows if row.class_name == class_name and row.phase_code == phase_code
    ]
    if not matching:
        return None

    riders = [
        SqorzOverlayRider(
            plate=row.plate,
            first_name=row.first_name,
            last_name=row.last_name,
            time_seconds=row.time_seconds,
        )
        for row in matching
    ]
    # Timed riders first, fastest first; untimed riders after, in whatever
    # order Sqorz returned them.
    riders.sort(key=lambda rider: (rider.time_seconds is None, rider.time_seconds or 0.0))

    first = matching[0]
    return SqorzOverlayRace(
        class_code=first.class_code,
        class_name=first.class_name,
        phase_code=phase_code,
        phase_name=first.phase_name,
        riders=riders,
    )


def build_overlay_state(
    sqorz: SqorzService,
    *,
    class_name: str | None,
    phase_code: str | None,
) -> SqorzOverlayState:
    if not sqorz.enabled:
        return SqorzOverlayState(enabled=False)
    fetch = sqorz.get_riders()
    race = build_race(fetch.riders, class_name=class_name, phase_code=phase_code)
    return SqorzOverlayState(
        enabled=True,
        reachable=fetch.reachable,
        stale=fetch.stale,
        age_seconds=fetch.age_seconds,
        error=fetch.error,
        race=race,
    )
