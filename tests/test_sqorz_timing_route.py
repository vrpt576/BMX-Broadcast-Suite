"""The standalone Sqorz overlay route: works with zero RaceManager wiring."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from connector.dependencies import get_sqorz_service
from connector.main import app
from connector.services.sqorz_service import SqorzService

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def load_event_fixture() -> dict:
    return json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))


def test_the_overlay_page_serves_without_any_current_moto_or_motoboard_dependency() -> None:
    """No dependency override is registered for MotoboardService or
    CurrentMotoService -- if this route touched either, the app's real
    (DB-backed) singletons would be constructed and this request would
    error out. It doesn't, proving the RaceManager-free boundary.
    """
    response = TestClient(app).get("/overlay/sqorz-timing")
    assert response.status_code == 200
    assert "SQORZ LIVE" in response.text


def test_api_current_disabled_by_default_returns_200(tmp_path: Path) -> None:
    app.dependency_overrides[get_sqorz_service] = lambda: SqorzService(enabled=False)
    response = TestClient(app).get("/api/sqorz/current")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["race"] is None
    app.dependency_overrides.clear()


def test_api_current_returns_a_real_race_from_the_fixture() -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="fixture")
    sqorz._get_json = lambda url: load_event_fixture()
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get("/api/sqorz/current")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["reachable"] is True
    assert body["race"] is not None
    assert body["race"]["riders"]
    app.dependency_overrides.clear()


def test_explicit_class_and_phase_query_params_select_the_race() -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="fixture")
    sqorz._get_json = lambda url: load_event_fixture()
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get(
        "/api/sqorz/current", params={"class": "11-12 Open", "phase": "M1"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["race"]["class_name"] == "11-12 Open"
    assert body["race"]["phase_code"] == "M1"
    app.dependency_overrides.clear()


def test_sqorz_phase_name_is_present_in_this_response_by_design() -> None:
    """Opposite rule from the lineup overlay's phase_label protection --
    this endpoint IS Sqorz's own view, so its phase wording is expected."""
    sqorz = SqorzService(enabled=True, mode="internet", event_id="fixture")
    sqorz._get_json = lambda url: load_event_fixture()
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get(
        "/api/sqorz/current", params={"class": "11-12 Open", "phase": "M1"}
    )

    assert response.json()["race"]["phase_name"] == "Moto 1"
    app.dependency_overrides.clear()
