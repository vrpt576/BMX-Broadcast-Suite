"""Broadcast-ready lineup for Sqorz-only mode.

Reuses CurrentLineup and LineupRider (connector/models.py) unchanged, so the
existing lineup overlay renders a Sqorz-only lineup exactly like a
RaceManager one -- no overlay-template changes needed for this module's own
sake. Reusing those models is a shared data CONTRACT, not a RaceManager
dependency: connector/models.py has no RaceManagerDatabase coupling of its
own, and this module never imports anything that does. See
docs/sqorz-only-mode.md.

No confidence-matching, unlike current_lineup_service.py's
_augment_with_sqorz (which cross-references a SEPARATE RaceManager rider
list against Sqorz by plate/name, because two independent systems need to
agree on identity there). Sqorz-only mode has exactly one source of rider
data -- Sqorz's own SqorzRiderTime rows ARE the lineup, not an overlay on
top of someone else's list. There is nothing to match, so
sqorz_matching.py is never imported here.

Sqorz's own phase_name becomes phase_label directly -- there is no
RaceManager finalization method to defer to (contrast with mixed mode,
where _augment_with_sqorz never touches phase_label at all). See
docs/racemanager-round-model.md for the RaceManager-mode half of this rule,
and CLAUDE.md.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from connector.models import CurrentLineup, LineupRider, RacePhase
from connector.services.sqorz_navigation_service import SqorzRaceSlot
from connector.services.sqorz_service import SqorzRiderTime, plausible_finish

_LEADING_DIGITS = re.compile(r"\d+")


def _display_moto_number(phase_code: str | None) -> int:
    """A stable integer derived from Sqorz's own phase code, for the
    overlay's existing "MOTO N" badge -- NOT a RaceManager moto_number and
    not always literally "which moto". Every phase code confirmed real
    (M1, M2, M3, 2F, 1F -- see tests/fixtures/sqorz/hoosier_day3_event.json)
    contains exactly one digit, extracted here: 1F -> 1, 2F -> 2 preserves
    those codes' own numbering rather than inventing an unrelated index."""
    if phase_code:
        match = _LEADING_DIGITS.search(phase_code)
        if match:
            return int(match.group())
    return 1


# Coarse categorisation only, for the overlay's existing phase-based
# CSS/badge handling -- NEVER the displayed round name (that's always
# phase_label, read straight from Sqorz's own phase_name below). Mirrors
# sqorz_matching.ROUND_PHASE_TO_SQORZ_CODE's vocabulary plus "2F"
# (confirmed real, not guessed -- see sqorz_navigation_service.py's
# _CANONICAL_PHASE_ORDER comment for where that evidence came from); not
# imported from there, for the same isolation reason
# sqorz_navigation_service.py doesn't import it either. An unrecognised
# code falls back to ROUND_1 -- an arbitrary but harmless choice, since
# this value is never shown as text.
_SQORZ_CODE_TO_RACE_PHASE = {
    "M1": RacePhase.ROUND_1,
    "M2": RacePhase.ROUND_2,
    "M3": RacePhase.ROUND_3,
    "2F": RacePhase.SEMIFINAL,
    "1F": RacePhase.MAIN,
}


def build_sqorz_only_lineup(
    riders_in_slot: Sequence[SqorzRiderTime], slot: SqorzRaceSlot
) -> CurrentLineup:
    """riders_in_slot must already be filtered to slot's own (class_code,
    phase_code) -- this function doesn't filter, mirroring
    sqorz_navigation_service's layering: catalog functions build slots,
    this builds a lineup for exactly one already-chosen slot."""
    lineup_riders = [
        LineupRider(
            gate=row.race_position,
            bike_number=row.plate,
            first_name=row.first_name or "",
            last_name=row.last_name or "",
            time_seconds=row.time_seconds,
            finish=plausible_finish(row.result),
        )
        for row in riders_in_slot
    ]
    lineup_riders.sort(key=lambda rider: (rider.gate is None, rider.gate or 999, rider.last_name))

    return CurrentLineup(
        moto_number=_display_moto_number(slot.phase_code),
        race_phase=_SQORZ_CODE_TO_RACE_PHASE.get(slot.phase_code or "", RacePhase.ROUND_1),
        phase_label=slot.phase_name,
        available_phases=[],
        class_name=slot.class_name or "Class not set",
        riders=lineup_riders,
        source="sqorz",
        sqorz_phase_code=slot.phase_code,
    )


def empty_sqorz_only_lineup() -> CurrentLineup:
    """Nothing selected yet -- see SqorzCurrentRaceService.get() returning
    None. A real, valid CurrentLineup with zero riders and an explanatory
    warning, not an error, consistent with how the overlay already
    tolerates "nothing to show yet" everywhere else."""
    return CurrentLineup(
        moto_number=0,
        race_phase=RacePhase.ROUND_1,
        phase_label=None,
        available_phases=[],
        class_name="No race selected",
        riders=[],
        source="sqorz",
        warning="No race has been selected yet in Sqorz-only mode.",
    )
