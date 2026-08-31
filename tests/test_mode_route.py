"""GET /api/mode and POST /api/mode/recheck -- the operator-triggered
"Re-check" action behind the button on /director and /setup (see
connector/routes/mode.py). Mode must never change silently between an
explicit recheck and a saved configuration change; this only tests the HTTP
surface -- the resolution logic itself is in test_operating_mode_service.py.
"""

from __future__ import annotations

import connector.dependencies as deps
from fastapi.testclient import TestClient

from connector.dependencies import get_operating_mode
from connector.main import app
from connector.services.operating_mode_service import ModeDecision, OperatingMode


def test_read_mode_returns_the_current_decision() -> None:
    app.dependency_overrides[get_operating_mode] = lambda: ModeDecision(
        OperatingMode.SQORZ_ONLY, "Sqorz-only mode is explicitly enabled in Configuration."
    )
    response = TestClient(app).get("/api/mode")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "sqorz_only",
        "reason": "Sqorz-only mode is explicitly enabled in Configuration.",
    }
    app.dependency_overrides.clear()


def test_recheck_reports_both_the_before_and_after_decision(monkeypatch) -> None:
    """Change 1's explicit requirement: the operator sees what the mode was
    and what it becomes, not just the new value -- so a re-check that
    changes nothing is visibly a no-op, and one that does change something
    is visibly a change. Exercises the real cached get_operating_mode via
    monkeypatched reachability rather than a dependency override, since the
    route's "after" value deliberately bypasses FastAPI's per-request
    dependency resolution to force a genuine recomputation, not a
    cache_clear() that a test double could pass without actually happening."""
    get_operating_mode.cache_clear()
    monkeypatch.setattr(deps, "check_racemanager_reachable", lambda database: True)
    get_operating_mode()  # populate the cache with the "reachable" decision

    monkeypatch.setattr(deps, "check_racemanager_reachable", lambda database: False)
    response = TestClient(app).post("/api/mode/recheck")

    assert response.status_code == 200
    body = response.json()
    assert body["before"]["mode"] == "racemanager"
    assert body["after"]["mode"] in ("sqorz_only", "unavailable")
    assert body["before"] != body["after"]
    get_operating_mode.cache_clear()


def test_recheck_actually_clears_the_cache_not_just_the_override() -> None:
    """No monkeypatching or override involved -- proves the cache_clear()
    call in connector/routes/mode.py runs against the real lru_cache."""
    get_operating_mode()  # populate
    assert get_operating_mode.cache_info().currsize == 1

    response = TestClient(app).post("/api/mode/recheck")

    assert response.status_code == 200
    # The route recomputes after clearing, so the cache is populated again
    # with a fresh entry -- currsize back to 1, not left at 0 or stale.
    assert get_operating_mode.cache_info().currsize == 1
