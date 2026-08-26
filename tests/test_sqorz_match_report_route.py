"""The visible match-report page/API and its alias-editing endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from connector.dependencies import get_sqorz_class_alias_store, get_sqorz_service
from connector.main import app
from connector.services.sqorz_class_alias_service import SqorzClassAliasStore
from connector.services.sqorz_matching import MatchReport
from connector.services.sqorz_service import SqorzService


def test_disabled_sqorz_reports_disabled_with_no_data() -> None:
    app.dependency_overrides[get_sqorz_service] = lambda: SqorzService(enabled=False)
    response = TestClient(app).get("/api/sqorz/match-report")
    assert response.status_code == 200
    body = response.json()
    assert body["sqorz_enabled"] is False
    assert body["report"] is None
    app.dependency_overrides.clear()


def test_no_report_computed_yet_returns_null_report_not_an_error() -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    sqorz._get_json = lambda url: {"classRanks": []}
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz
    response = TestClient(app).get("/api/sqorz/match-report")
    assert response.status_code == 200
    assert response.json()["report"] is None
    app.dependency_overrides.clear()


def test_a_computed_report_is_visible_with_counts_and_unmatched_names() -> None:
    sqorz = SqorzService(enabled=True, mode="internet", event_id="e")
    sqorz._get_json = lambda url: {
        "classRanks": [
            {
                "classCode": "C1",
                "className": "11-12 Open",
                "competitorRankSummaries": [
                    {
                        "plate": "20",
                        "firstName": "Racyn",
                        "lastName": "Murfin",
                        "competitorRankDetails": [{"phaseCode": "M1", "time": "47.529"}],
                    }
                ],
            }
        ]
    }
    sqorz.last_match_report = MatchReport(
        counts={"exact": 1, "strong": 0, "weak": 0, "none": 1},
        unmatched_bbs=["Jane Doe"],
        unmatched_sqorz=["RACYN MURFIN"],
        class_match_path="class_name",
        ambiguous_plates=["11-12 Open #9 (Sqorz): Dylan Dobelle, Wade Hinderlider"],
    )
    sqorz.last_match_class_name = "11-12 Open"
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz

    response = TestClient(app).get("/api/sqorz/match-report")

    assert response.status_code == 200
    body = response.json()
    assert body["current_class_name"] == "11-12 Open"
    assert body["report"]["counts"] == {"exact": 1, "strong": 0, "weak": 0, "none": 1}
    assert body["report"]["unmatched_bbs"] == ["Jane Doe"]
    assert body["report"]["unmatched_sqorz"] == ["RACYN MURFIN"]
    assert "Dobelle" in body["report"]["ambiguous_plates"][0]
    assert "11-12 Open" in body["sqorz_classes"]
    app.dependency_overrides.clear()


def test_saving_an_alias_round_trips_through_the_api(tmp_path: Path) -> None:
    store = SqorzClassAliasStore(tmp_path / "aliases.json")
    app.dependency_overrides[get_sqorz_class_alias_store] = lambda: store

    response = TestClient(app).put(
        "/api/sqorz/aliases",
        json={"bbs_class_name": "11-12 Open", "sqorz_class_name": "2204"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is True
    assert body["aliases"] == {"11-12 Open": "2204"}
    assert store.get_alias("11-12 Open") == "2204"
    app.dependency_overrides.clear()


def test_clearing_an_alias_removes_it(tmp_path: Path) -> None:
    store = SqorzClassAliasStore(tmp_path / "aliases.json")
    store.set_alias("11-12 Open", "2204")
    app.dependency_overrides[get_sqorz_class_alias_store] = lambda: store

    response = TestClient(app).put(
        "/api/sqorz/aliases",
        json={"bbs_class_name": "11-12 Open", "sqorz_class_name": None},
    )

    assert response.status_code == 200
    assert response.json()["aliases"] == {}
    assert store.get_alias("11-12 Open") is None
    app.dependency_overrides.clear()


def test_saving_without_a_bbs_class_name_fails_cleanly() -> None:
    store = SqorzClassAliasStore(None)
    app.dependency_overrides[get_sqorz_class_alias_store] = lambda: store

    response = TestClient(app).put("/api/sqorz/aliases", json={"sqorz_class_name": "2204"})

    assert response.status_code == 200
    assert response.json()["saved"] is False
    app.dependency_overrides.clear()


def test_the_page_serves_without_any_racemanager_dependency() -> None:
    response = TestClient(app).get("/sqorz-match-report")
    assert response.status_code == 200
    assert "Sqorz Match Report" in response.text
