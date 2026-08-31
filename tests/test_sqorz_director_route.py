"""Sqorz-only mode's Director controls -- a fully separate route surface
from /api/current, tested end-to-end through the real HTTP routes. Internet
mode tests use the real captured fixture; LAN mode tests use synthetic data
(no real getPhaseSummaries payload has ever been captured -- see
sqorz_navigation_service.py's module docstring).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from connector.dependencies import get_sqorz_current_race_service, get_sqorz_service
from connector.main import app
from connector.services.sqorz_current_race_service import SqorzCurrentRaceService
from connector.services.sqorz_service import SqorzService

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sqorz"


def load_real_payload() -> dict:
    return json.loads((FIXTURES / "hoosier_day3_event.json").read_text(encoding="utf-8"))


def internet_sqorz() -> SqorzService:
    service = SqorzService(enabled=True, mode="internet", event_id="e")
    service._get_json = lambda url: load_real_payload()
    return service


def override(tmp_path: Path, sqorz: SqorzService):
    current_race = SqorzCurrentRaceService(tmp_path / "sqorz_current.json")
    app.dependency_overrides[get_sqorz_service] = lambda: sqorz
    app.dependency_overrides[get_sqorz_current_race_service] = lambda: current_race
    return current_race


def clear():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /state
# ---------------------------------------------------------------------------


def test_state_with_nothing_selected_shows_no_selection(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())

    response = TestClient(app).get("/api/sqorz-director/state")

    assert response.status_code == 200
    body = response.json()
    assert body["selected"] is None
    assert body["mode"] == "internet"
    clear()


def test_state_in_internet_mode_lists_real_classes_alphabetically(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())

    body = TestClient(app).get("/api/sqorz-director/state").json()

    names = [c["class_name"] for c in body["classes"]]
    assert names == sorted(names, key=str.lower)
    assert "12 Expert" in names
    clear()


def test_state_in_lan_mode_never_exposes_a_class_picker(tmp_path: Path) -> None:
    """Change 3: the class/event picker is internet-mode only -- LAN mode
    has no such list, per the approved design."""
    sqorz = SqorzService(enabled=True, mode="lan", host="scoring")
    sqorz._call_lan = lambda func, args: {}
    override(tmp_path, sqorz)

    body = TestClient(app).get("/api/sqorz-director/state").json()

    assert "classes" not in body
    assert body["mode"] == "lan"
    clear()


# ---------------------------------------------------------------------------
# select-class / jump-to-recent -- internet/file mode
# ---------------------------------------------------------------------------


def test_select_class_lands_on_the_first_phase(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())

    body = TestClient(app).post("/api/sqorz-director/select-class/308").json()

    assert body["selected"]["class_code"] == "308"
    assert body["selected"]["phase_code"] == "M1"
    clear()


def test_select_class_with_an_unknown_class_code_leaves_nothing_selected(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())

    body = TestClient(app).post("/api/sqorz-director/select-class/not-a-real-class").json()

    assert body["selected"] is None
    clear()


def test_jump_to_recent_moves_to_the_furthest_phase_with_a_time(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())
    TestClient(app).post("/api/sqorz-director/select-class/308")

    body = TestClient(app).post("/api/sqorz-director/jump-to-recent").json()

    assert body["selected"]["phase_code"] == "1F"  # every 1F row in the fixture has a real time
    clear()


def test_jump_to_recent_with_no_class_selected_is_a_harmless_no_op(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())

    response = TestClient(app).post("/api/sqorz-director/jump-to-recent")

    assert response.status_code == 200
    assert response.json()["selected"] is None
    clear()


# ---------------------------------------------------------------------------
# next/previous -- internet/file mode (within selected class only)
# ---------------------------------------------------------------------------


def test_next_within_a_class_walks_the_real_phase_sequence(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())
    TestClient(app).post("/api/sqorz-director/select-class/308")  # lands on M1

    client = TestClient(app)
    codes = [client.post("/api/sqorz-director/next").json()["selected"]["phase_code"] for _ in range(3)]

    assert codes == ["M2", "2F", "1F"]
    clear()


def test_next_then_previous_is_an_exact_inverse_over_http(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())
    TestClient(app).post("/api/sqorz-director/select-class/308")
    client = TestClient(app)

    forward = client.post("/api/sqorz-director/next").json()
    back = client.post("/api/sqorz-director/previous").json()

    assert back["selected"] == {"class_code": "308", "class_name": "12 Expert", "phase_code": "M1", "phase_name": "Moto 1"}
    assert forward["selected"]["phase_code"] == "M2"
    clear()


def test_next_clamps_at_the_last_phase_in_the_class(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())
    client = TestClient(app)
    client.post("/api/sqorz-director/select-class/308")
    for _ in range(10):  # walk well past the end
        client.post("/api/sqorz-director/next")

    body = client.post("/api/sqorz-director/next").json()

    assert body["selected"]["phase_code"] == "1F"  # the real last phase for this class
    clear()


def test_next_with_no_class_selected_yet_is_a_no_op_not_a_crash(tmp_path: Path) -> None:
    override(tmp_path, internet_sqorz())

    response = TestClient(app).post("/api/sqorz-director/next")

    assert response.status_code == 200
    assert response.json()["selected"] is None
    clear()


def test_next_never_crosses_into_a_different_class(tmp_path: Path) -> None:
    """The internet/file-mode contract: Next/Previous stays within the
    selected class no matter how far it steps -- never spills into another
    class's phases even at the catalog boundary."""
    override(tmp_path, internet_sqorz())
    client = TestClient(app)
    client.post("/api/sqorz-director/select-class/308")
    for _ in range(20):
        client.post("/api/sqorz-director/next")

    body = client.post("/api/sqorz-director/next").json()

    assert body["selected"]["class_code"] == "308"
    clear()


# ---------------------------------------------------------------------------
# next/previous -- LAN mode (full-event catalog). Synthetic data: no real
# getPhaseSummaries payload has ever been captured.
# ---------------------------------------------------------------------------


def lan_sqorz() -> SqorzService:
    service = SqorzService(enabled=True, mode="lan", host="scoring")

    def fake_call_lan(func: str, args: list) -> object:
        if func == "getPhaseSummaries":
            return {
                "phaseSummaries": [
                    {"classCode": "C1", "phaseCode": "M1"},
                    {"classCode": "C2", "phaseCode": "M1"},
                ]
            }
        if func == "getPhaseBlockSummaries":
            return {
                "phaseBlockSummaries": [
                    {"classCode": "C1", "phaseBlockCode": "M1", "className": "Alpha"},
                    {"classCode": "C2", "phaseBlockCode": "M1", "className": "Beta"},
                ]
            }
        return {
            "competitors": [
                {
                    "plate": "1",
                    "lastName": "RIDER",
                    "competitorRankDetails": [{"phaseCode": "M1", "time": "40.0"}],
                }
            ]
        }

    service._call_lan = fake_call_lan
    return service


def test_lan_mode_next_walks_the_verified_cross_class_order(tmp_path: Path) -> None:
    override(tmp_path, lan_sqorz())
    client = TestClient(app)

    first = client.post("/api/sqorz-director/next").json()
    second = client.post("/api/sqorz-director/next").json()

    assert first["selected"]["class_code"] == "C1"
    assert second["selected"]["class_code"] == "C2"
    clear()


def test_lan_mode_ignores_select_class_and_jump_to_recent(tmp_path: Path) -> None:
    """Those two endpoints exist for internet/file mode's class-scoped
    model -- calling them in LAN mode must not crash, even though the
    Director UI never surfaces them there."""
    override(tmp_path, lan_sqorz())
    response = TestClient(app).post("/api/sqorz-director/jump-to-recent")
    assert response.status_code == 200
    clear()
