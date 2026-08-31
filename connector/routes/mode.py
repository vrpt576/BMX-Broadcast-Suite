"""The current operating mode (RaceManager / Sqorz-only / unavailable) and
the operator-triggered "Re-check" action -- see
connector/services/operating_mode_service.py for the resolution logic and
why it's cached rather than re-evaluated per request.

Deliberately two endpoints, not one: GET is read-only and safe to poll or
load on every /director and /setup page load; POST is the only thing that
clears the cache and re-runs detection, so mode changes only ever happen
when an operator explicitly asks, never as a side effect of viewing a page.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from connector.dependencies import get_operating_mode
from connector.services.operating_mode_service import ModeDecision

router = APIRouter(tags=["mode"])


def _serialize(decision: ModeDecision) -> dict[str, Any]:
    return {"mode": decision.mode.value, "reason": decision.reason}


@router.get("/mode")
def read_mode(decision: ModeDecision = Depends(get_operating_mode)) -> dict[str, Any]:
    return _serialize(decision)


@router.post("/mode/recheck")
def recheck_mode(decision: ModeDecision = Depends(get_operating_mode)) -> dict[str, Any]:
    before = _serialize(decision)
    get_operating_mode.cache_clear()
    after = _serialize(get_operating_mode())
    return {"before": before, "after": after}
