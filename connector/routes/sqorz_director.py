"""Sqorz-only mode's Director controls -- fully separate from
connector/routes/current.py, never importing it or anything it depends on.
RaceManager mode's Next/Previous/phase-select controls keep working through
current.py exactly as before; these are Sqorz-only mode's own equivalents,
repurposing the same physical buttons in the Director UI (see
docs/sqorz-only-mode.md for the control-mapping table).

Two genuinely different navigation scopes, chosen per Sqorz's own mode
setting, not a per-request guess:

  LAN mode steps through _active_catalog()'s full-event catalog (every
  class, ordered primarily by getPhaseSummaries -- see
  sqorz_navigation_service.build_lan_catalog).

  Internet/file mode has no cross-class catalog at all -- _active_catalog()
  returns the phase sequence for whichever class is currently selected
  (build_class_phase_sequence), or an empty list before any class has been
  picked. GET /sqorz-director/classes and POST /sqorz-director/select-class
  exist only for this scope; calling them in LAN mode is harmless (the
  Director UI never shows the class picker there -- see the control-mapping
  table) but returns real, honest data either way: an empty class list is
  never fabricated as an error.

No mode check gates these routes: SqorzService already degrades safely
(get_riders() returns no riders, never raises) when Sqorz isn't the active
mode, so calling them outside Sqorz-only mode is a harmless no-op, not a
special case to guard against.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from connector.dependencies import get_sqorz_current_race_service, get_sqorz_service
from connector.services.sqorz_current_race_service import SqorzCurrentRace, SqorzCurrentRaceService
from connector.services.sqorz_navigation_service import (
    SqorzRaceSlot,
    build_class_catalog,
    build_class_phase_sequence,
    build_lan_catalog,
    find_most_recent_activity,
    step,
)
from connector.services.sqorz_service import SqorzService

router = APIRouter(prefix="/sqorz-director", tags=["sqorz-director"])


def _active_catalog(sqorz: SqorzService, current: SqorzCurrentRace | None) -> list[SqorzRaceSlot]:
    riders = sqorz.get_riders().riders
    if sqorz.mode == "lan":
        return build_lan_catalog(riders, sqorz.last_phase_summaries_order)
    class_code = current.class_code if current is not None else None
    if class_code is None:
        return []
    return build_class_phase_sequence(riders, class_code)


def _selected_dict(current: SqorzCurrentRace | None) -> dict[str, Any] | None:
    if current is None:
        return None
    return {
        "class_code": current.class_code,
        "class_name": current.class_name,
        "phase_code": current.phase_code,
        "phase_name": current.phase_name,
    }


def _state(sqorz: SqorzService, sqorz_current_race: SqorzCurrentRaceService) -> dict[str, Any]:
    current = sqorz_current_race.get()
    state: dict[str, Any] = {
        "mode": sqorz.mode,
        "selected": _selected_dict(current),
    }
    if sqorz.mode != "lan":
        state["classes"] = [
            {"class_code": summary.class_code, "class_name": summary.class_name}
            for summary in build_class_catalog(sqorz.get_riders().riders)
        ]
    return state


@router.get("/state")
def get_state(
    sqorz: SqorzService = Depends(get_sqorz_service),
    sqorz_current_race: SqorzCurrentRaceService = Depends(get_sqorz_current_race_service),
) -> dict[str, Any]:
    return _state(sqorz, sqorz_current_race)


@router.get("/events")
def get_events(sqorz: SqorzService = Depends(get_sqorz_service)) -> list[dict[str, Any]]:
    """Internet mode's event picker (Change 3) -- switching which Sqorz
    event BBS polls is a configuration change (BBS_SQORZ_EVENT_ID), saved
    through the existing /api/configuration endpoint like any other
    setting, not a new write endpoint here. This route only lists what's
    available to pick from. Harmless in LAN/file mode or without an org
    code configured: fetch_org_events() returns [] rather than an error."""
    return [
        {"event_id": event.event_id, "event_name": event.event_name, "event_date": event.event_date}
        for event in sqorz.fetch_org_events()
    ]


@router.post("/select-class/{class_code}")
def select_class(
    class_code: str,
    sqorz: SqorzService = Depends(get_sqorz_service),
    sqorz_current_race: SqorzCurrentRaceService = Depends(get_sqorz_current_race_service),
) -> dict[str, Any]:
    """Internet/file mode only: pick a class and land on its first phase --
    a fresh, predictable starting point. Use POST /jump-to-recent
    afterward for "skip ahead to where scoring actually is" instead."""
    sequence = build_class_phase_sequence(sqorz.get_riders().riders, class_code)
    if sequence:
        sqorz_current_race.select(sequence[0])
    return _state(sqorz, sqorz_current_race)


@router.post("/jump-to-recent")
def jump_to_recent(
    sqorz: SqorzService = Depends(get_sqorz_service),
    sqorz_current_race: SqorzCurrentRaceService = Depends(get_sqorz_current_race_service),
) -> dict[str, Any]:
    """Internet/file mode only: jump to the furthest phase with a recorded
    time in the currently selected class. A no-op if no class is selected
    yet -- select a class first."""
    current = sqorz_current_race.get()
    if current is not None and current.class_code is not None:
        slot = find_most_recent_activity(sqorz.get_riders().riders, current.class_code)
        if slot is not None:
            sqorz_current_race.select(slot)
    return _state(sqorz, sqorz_current_race)


@router.post("/next")
def next_race(
    sqorz: SqorzService = Depends(get_sqorz_service),
    sqorz_current_race: SqorzCurrentRaceService = Depends(get_sqorz_current_race_service),
) -> dict[str, Any]:
    return _step(sqorz, sqorz_current_race, +1)


@router.post("/previous")
def previous_race(
    sqorz: SqorzService = Depends(get_sqorz_service),
    sqorz_current_race: SqorzCurrentRaceService = Depends(get_sqorz_current_race_service),
) -> dict[str, Any]:
    return _step(sqorz, sqorz_current_race, -1)


def _step(sqorz: SqorzService, sqorz_current_race: SqorzCurrentRaceService, direction: int) -> dict[str, Any]:
    current = sqorz_current_race.get()
    catalog = _active_catalog(sqorz, current)
    current_key = (current.class_code, current.phase_code) if current is not None else None
    target = step(catalog, current_key, direction)
    if target is not None:
        sqorz_current_race.select(target)
    return _state(sqorz, sqorz_current_race)
