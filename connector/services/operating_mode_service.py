"""Resolves BBS's current operating mode: full RaceManager integration, or
Sqorz-only (no RaceManager access at all). See docs/sqorz-only-mode.md for
the full design.

Computed once and cached (connector/dependencies.py::get_operating_mode(),
lru_cache'd the same way get_database()/get_sqorz_service() already are)
rather than re-evaluated on every request -- a transient RaceManager
network blip mid-event must not silently swap the operator's entire
navigation model out from under them for the rest of the event. The cache
is cleared in two places, both deliberate: when configuration is saved
(ConfigurationService.save(), same as get_database()/get_sqorz_service()
already are), and when an operator explicitly asks BBS to look again --
the "Re-check" action on /director and /setup (see
connector/routes/mode.py). Mode never changes silently between those two
moments; a track running RaceManager sees no behavior change of any kind
from this module unless one of those two things happens.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OperatingMode(str, Enum):
    RACEMANAGER = "racemanager"
    SQORZ_ONLY = "sqorz_only"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ModeDecision:
    mode: OperatingMode
    reason: str


def resolve_operating_mode(
    *, racemanager_reachable: bool, sqorz_enabled: bool, force_sqorz_only: bool
) -> ModeDecision:
    """Never asks the operator to pick a mode -- detects what's usable and
    says why in plain language, so the reason is visible on /director and
    /setup, not just implied by which controls happen to be present.

    force_sqorz_only is the one explicit override this project's design
    calls for: a track with both RaceManager and Sqorz configured that
    wants Sqorz-only anyway. Everything else here is automatic detection.
    Order matters: the override is checked first (an operator's explicit
    choice always wins), then RaceManager reachability (the common case,
    checked before Sqorz so a working RaceManager install is never
    second-guessed), then Sqorz as the fallback, then "neither" -- the
    existing "fix your setup" state, unchanged from before this module
    existed.
    """
    if force_sqorz_only and sqorz_enabled:
        return ModeDecision(
            OperatingMode.SQORZ_ONLY,
            "Sqorz-only mode is explicitly enabled in Configuration.",
        )
    if racemanager_reachable:
        return ModeDecision(OperatingMode.RACEMANAGER, "Connected to RaceManager.")
    if sqorz_enabled:
        return ModeDecision(
            OperatingMode.SQORZ_ONLY,
            "RaceManager is not configured or not reachable, and Sqorz is "
            "configured, so BBS is running Sqorz-only.",
        )
    return ModeDecision(
        OperatingMode.UNAVAILABLE,
        "Neither RaceManager nor Sqorz is usable yet -- see /setup.",
    )


def check_racemanager_reachable(database: Any) -> bool:
    """A minimal, real connectivity check -- the same one-line query
    DiagnosticsService's own database check runs, isolated here so mode
    resolution doesn't need to run the other six diagnostic checks
    (driver, network, pyodbc, configuration...) just to answer one
    yes/no question. Never raises: an unreachable database, missing
    driver, or blank configuration are all just "not reachable right
    now" from this function's point of view, exactly as they should be
    for a mode decision -- the *reason* a track is in Sqorz-only mode is
    reported elsewhere (Diagnostics), not here.
    """
    try:
        database.fetch_one("SELECT 1 AS ok")
        return True
    except Exception:  # noqa: BLE001 - "not reachable" is a normal, expected outcome
        return False
