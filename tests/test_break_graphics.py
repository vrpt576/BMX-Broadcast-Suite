from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from connector.dependencies import get_current_moto_service, get_results_roll_service
from connector.main import app as connector_app
from connector.models import ActiveGraphic, BreakPreset, CurrentMotoUpdate, RacePhase
from connector.routes.breaks import BREAK_HTML, break_presets, router, show_break
from connector.routes.director import DIRECTOR_HTML
from connector.services.current_moto_service import CurrentMotoService


BOARD_ID = UUID("d726697c-36e3-4a4c-b21b-c65058dc31bf")
CLASS_ID = UUID("95379986-aef2-4427-b647-d282e14b3474")
ROUND_ID = UUID("e3bde226-ce52-4aed-a433-ebc2e35cd934")
GROUP_ID = UUID("040748b2-d4a0-472d-b818-4f61b55f511f")


class RecordingRoll:
    def __init__(self) -> None:
        self.pause_calls = 0

    def pause_if_active(self):
        self.pause_calls += 1


def current_service(tmp_path: Path) -> CurrentMotoService:
    service = CurrentMotoService(tmp_path / "current.json")
    service.set(
        CurrentMotoUpdate(
            moto_number=25,
            race_phase=RacePhase.MAIN,
            phase_label="Main",
            class_name="5 & Under Intermediate",
            motoboard_id=BOARD_ID,
            class_id=CLASS_ID,
            round_type_id=1,
            round_id=ROUND_ID,
            motogroup_id=GROUP_ID,
            round_index=1,
        )
    )
    return service


def race_position(service: CurrentMotoService) -> dict[str, object]:
    state = service.get()
    return state.model_dump(exclude={"active_graphic", "updated_at"})


@pytest.mark.parametrize(
    ("preset", "graphic"),
    (
        (BreakPreset.ROUND_1, ActiveGraphic.ROUND_1_BREAK),
        (BreakPreset.MAIN, ActiveGraphic.MAIN_BREAK),
    ),
)
def test_show_break_pauses_results_without_mutating_race_position(
    tmp_path: Path,
    preset: BreakPreset,
    graphic: ActiveGraphic,
) -> None:
    current = current_service(tmp_path)
    roll = RecordingRoll()
    before = race_position(current)

    state = show_break(preset, current=current, results_roll=roll)

    assert state.active_graphic == graphic
    assert race_position(current) == before
    assert roll.pause_calls == 1


def test_break_api_exposes_only_validated_presets() -> None:
    assert break_presets() == [BreakPreset.ROUND_1, BreakPreset.MAIN]
    assert {route.path for route in router.routes} == {
        "/breaks/presets",
        "/breaks/show/{preset}",
    }
    with pytest.raises(ValueError):
        TypeAdapter(BreakPreset).validate_python("quarterfinal")

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_moto_service] = lambda: object()
    app.dependency_overrides[get_results_roll_service] = lambda: object()
    response = TestClient(app).post("/breaks/show/quarterfinal")
    assert response.status_code == 422


def test_break_overlay_is_shared_theme_aware_and_broadcast_safe() -> None:
    assert "/overlay/break" in {route.path for route in connector_app.routes}
    assert "ROUND 1 BREAK" in BREAK_HTML
    assert "MAIN BREAK" in BREAK_HTML
    assert "round_1_break" in BREAK_HTML
    assert "main_break" in BREAK_HTML
    assert "/api/themes/" in BREAK_HTML
    assert "inset:5%" in BREAK_HTML
    assert "overflow:hidden" in BREAK_HTML
    assert "setInterval(load,1000)" in BREAK_HTML


def test_director_has_both_break_buttons_without_shortcut_conflicts() -> None:
    assert 'data-break="round_1"' in DIRECTOR_HTML
    assert 'data-break="main"' in DIRECTOR_HTML
    assert "Show Round 1 Break" in DIRECTOR_HTML
    assert "Show Main Break" in DIRECTOR_HTML
    assert "request(`/api/breaks/show/${preset}`" in DIRECTOR_HTML
    assert "event.key.toLowerCase()==='b'" not in DIRECTOR_HTML
