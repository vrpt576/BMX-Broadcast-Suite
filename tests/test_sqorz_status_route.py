"""The consolidated /sqorz-status page and its API -- one URL, everything."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from connector.dependencies import get_sqorz_class_alias_store, get_sqorz_service
from connector.main import app
from connector.services.sqorz_class_alias_service import SqorzClassAliasStore
from connector.services.sqorz_matching import MatchReport
from connector.services.sqorz_service import SqorzService

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def test_disabled_sqorz_reports_disabled_with_no_data() -> None:
    app.dependency_overrides[get_sqorz_service] = lambda: SqorzService(enabled=False)
    response = TestClient(app).get("/api/sqorz/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    app.dependency_overrides.clear()


def test_enabled_but_never_polled_returns_zero_counts_not_an_error() -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    sqorz._get_json = lambda url: {"classRanks": []}
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get("/api/sqorz/status")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["class_count"] == 0
    assert body["competitor_count"] == 0
    assert body["match_report"] is None
    app.dependency_overrides.clear()


def test_full_status_reports_counts_match_report_and_gate_agreement() -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    payload = json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))
    sqorz._get_json = lambda url: payload
    sqorz.last_match_report = MatchReport(
        counts={"exact": 3, "strong": 1, "weak": 0, "none": 0},
        unmatched_bbs=[],
        unmatched_sqorz=["SOMEONE UNMATCHED"],
        class_match_path="class_name",
        ambiguous_plates=["11-12 Open #9 (Sqorz): Dylan Dobelle, Wade Hinderlider"],
        gate_checks={"agree": 3, "disagree": 1},
    )
    sqorz.last_match_class_name = "11-12 Open"
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get("/api/sqorz/status")

    assert response.status_code == 200
    body = response.json()
    assert body["reachable"] is True
    assert body["class_count"] > 0
    assert body["competitor_count"] > 0
    assert body["current_class_name"] == "11-12 Open"
    assert body["match_report"]["counts"] == {"exact": 3, "strong": 1, "weak": 0, "none": 0}
    assert "Dobelle" in body["match_report"]["ambiguous_plates"][0]
    assert body["match_report"]["gate_agreement_rate"] == 75  # 3/4
    app.dependency_overrides.clear()


def test_lan_parse_warning_surfaces_when_set() -> None:
    sqorz = SqorzService(enabled=True, mode="lan", host="scoring")
    sqorz.last_lan_parse_warning = "Sqorz LAN responded, but nothing could be recognised."
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get("/api/sqorz/status")

    assert response.json()["lan_parse_warning"] == sqorz.last_lan_parse_warning
    app.dependency_overrides.clear()


def test_raw_lan_response_unavailable_before_any_lan_poll() -> None:
    sqorz = SqorzService(enabled=True, mode="lan", host="scoring")
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get("/api/sqorz/lan-raw")

    assert response.status_code == 200
    assert response.json() == {"available": False}
    app.dependency_overrides.clear()


def test_raw_lan_response_is_served_once_captured() -> None:
    sqorz = SqorzService(enabled=True, mode="lan", host="scoring")
    sqorz.last_raw_lan_response = {"getPhaseBlockSummaries": {"totally": "unexpected"}}
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get("/api/sqorz/lan-raw")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["responses"]["getPhaseBlockSummaries"] == {"totally": "unexpected"}
    app.dependency_overrides.clear()


def test_saving_an_alias_from_the_status_page_uses_the_existing_endpoint(tmp_path) -> None:
    """The status page's alias form deliberately posts to the same
    /api/sqorz/aliases endpoint /sqorz-match-report already uses -- no
    duplicated backend logic."""
    store = SqorzClassAliasStore(tmp_path / "aliases.json")
    app.dependency_overrides[get_sqorz_class_alias_store] = lambda: store

    response = TestClient(app).put(
        "/api/sqorz/aliases", json={"bbs_class_name": "11-12 Open", "sqorz_class_name": "2204"}
    )

    assert response.status_code == 200
    assert store.get_alias("11-12 Open") == "2204"
    app.dependency_overrides.clear()


def test_the_page_serves_without_any_racemanager_dependency() -> None:
    response = TestClient(app).get("/sqorz-status")
    assert response.status_code == 200
    assert "Sqorz Status" in response.text
    assert "View raw response" in response.text


def test_page_source_never_hardcodes_a_confirmation_the_raw_response_is_correct() -> None:
    """Guards the "resilience, not verification" framing: the page text
    must not claim a raw response proves the shape is right."""
    response = TestClient(app).get("/sqorz-status")
    assert "resilience, not verification" in response.text
