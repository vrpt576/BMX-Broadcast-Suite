from fastapi import HTTPException

from connector.models import ActiveGraphic, ResultsRollStart, ResultsRollState
from connector.routes.current import select_graphic
from connector.routes.results import (
    current_results,
    next_result,
    pause_results_roll,
    previous_result,
    resume_results_roll,
    router,
    show_current_results,
    start_results_roll,
    stop_results_roll,
)
from connector.services.results_roll_service import ResultsRollUnavailableError


class RecordingRoll:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def _record(self, value: object) -> ResultsRollState:
        self.calls.append(value)
        return ResultsRollState()

    def show_current(self):
        return self._record("show-current")

    def start(self, request):
        return self._record(request)

    def pause(self):
        return self._record("pause")

    def resume(self):
        return self._record("resume")

    def previous(self):
        return self._record("previous")

    def next(self):
        return self._record("next")

    def stop(self):
        return self._record("stop")

    def pause_if_active(self):
        return self._record("pause-if-active")


class RecordingCurrent:
    def __init__(self) -> None:
        self.graphic = None

    def set_graphic(self, graphic):
        self.graphic = graphic
        return graphic


def test_results_router_exposes_all_control_endpoints() -> None:
    paths = {route.path for route in router.routes}
    assert paths >= {
        "/results/current",
        "/results/status",
        "/results/show-current",
        "/results/start",
        "/results/pause",
        "/results/resume",
        "/results/previous",
        "/results/next",
        "/results/stop",
    }


def test_results_route_controls_delegate_to_server_owned_service() -> None:
    service = RecordingRoll()
    request = ResultsRollStart(start_from="current", interval_seconds=12)

    show_current_results(service=service)
    start_results_roll(request, service=service)
    pause_results_roll(service=service)
    resume_results_roll(service=service)
    previous_result(service=service)
    next_result(service=service)
    stop_results_roll(service=service)

    assert service.calls == [
        "show-current",
        request,
        "pause",
        "resume",
        "previous",
        "next",
        "stop",
    ]


def test_results_control_reports_unavailable_catalog_as_validation_error() -> None:
    class Unavailable(RecordingRoll):
        def start(self, request):
            raise ResultsRollUnavailableError("No official results are available.")

    try:
        start_results_roll(ResultsRollStart(), service=Unavailable())
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "No official results are available."
    else:  # pragma: no cover
        raise AssertionError("Unavailable Results Roll should return HTTP 422")


def test_current_results_rejects_non_main_selection_as_validation_error() -> None:
    class Unavailable(RecordingRoll):
        def current_result(self, *, demo=False):
            raise ResultsRollUnavailableError("Results are Main-only.")

    try:
        current_results(demo=False, service=Unavailable())
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Results are Main-only."
    else:  # pragma: no cover
        raise AssertionError("Non-Main current results should return HTTP 422")


def test_hide_all_pauses_results_roll_before_changing_graphic() -> None:
    current = RecordingCurrent()
    roll = RecordingRoll()

    result = select_graphic(ActiveGraphic.HIDDEN, service=current, results_roll=roll)

    assert result == ActiveGraphic.HIDDEN
    assert current.graphic == ActiveGraphic.HIDDEN
    assert roll.calls == ["pause-if-active"]


def test_selecting_results_does_not_pause_results_roll() -> None:
    current = RecordingCurrent()
    roll = RecordingRoll()

    select_graphic(ActiveGraphic.RESULTS, service=current, results_roll=roll)

    assert roll.calls == []
