"""The one explicitly named exception to Sqorz-only mode's isolation from
RaceManager.

OBS is configured with a single fixed Browser Source URL per track
(/overlay/lineup) -- there is no way for the operator to point it at two
different URLs depending on mode, so GET /api/lineup/current must serve the
right lineup regardless of which mode BBS is running in. That branch has to
live somewhere; it is kept to exactly this one small function, reviewed
here and nowhere else. current_lineup_service.py and sqorz_lineup_service.py
remain mutually unaware of each other -- neither imports the other, and
nothing in either file knows this dispatcher exists.
"""

from __future__ import annotations

from uuid import UUID

from connector.models import CurrentLineup
from connector.services.current_lineup_service import CurrentLineupService
from connector.services.operating_mode_service import ModeDecision, OperatingMode
from connector.services.sqorz_current_race_service import SqorzCurrentRaceService
from connector.services.sqorz_lineup_service import (
    build_sqorz_only_lineup,
    empty_sqorz_only_lineup,
)
from connector.services.sqorz_navigation_service import SqorzRaceSlot
from connector.services.sqorz_service import SqorzService


def resolve_current_lineup(
    *,
    mode: ModeDecision,
    racemanager_lineup: CurrentLineupService,
    sqorz_current_race: SqorzCurrentRaceService,
    sqorz: SqorzService,
    demo: bool = False,
    motoboard_id: UUID | None = None,
) -> CurrentLineup:
    if mode.mode is not OperatingMode.SQORZ_ONLY:
        return racemanager_lineup.get(demo=demo, motoboard_id=motoboard_id)

    current = sqorz_current_race.get()
    if current is None:
        return empty_sqorz_only_lineup()

    slot = SqorzRaceSlot(
        class_code=current.class_code,
        class_name=current.class_name,
        phase_code=current.phase_code,
        phase_name=current.phase_name,
        has_recorded_time=False,
    )
    riders_in_slot = [
        row
        for row in sqorz.get_riders().riders
        if row.class_code == current.class_code and row.phase_code == current.phase_code
    ]
    return build_sqorz_only_lineup(riders_in_slot, slot)
