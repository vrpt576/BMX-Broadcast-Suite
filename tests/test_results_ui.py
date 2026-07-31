from connector.routes.director import DIRECTOR_HTML
from connector.routes.results import RESULTS_HTML


def test_director_exposes_complete_results_roll_controls() -> None:
    for identifier in (
        "show-current-results",
        "results-start-button",
        "results-pause",
        "results-resume",
        "results-previous",
        "results-next",
        "results-stop",
        "results-interval",
        "results-status",
    ):
        assert f'id="{identifier}"' in DIRECTOR_HTML
    assert "Experimental" not in DIRECTOR_HTML
    assert "interval_seconds" in DIRECTOR_HTML
    assert "/api/results/status" in DIRECTOR_HTML


def test_results_overlay_is_broadcast_safe_and_shows_progress() -> None:
    assert "MOTO ${s.moto_number} RESULTS" in RESULTS_HTML
    assert "MOTO ${s.progress_index} OF ${s.progress_total}" in RESULTS_HTML
    assert "OFFICIAL RESULTS" in RESULTS_HTML
    assert "INCOMPLETE RESULTS" in RESULTS_HTML
    assert "s.riders.slice(0,8)" in RESULTS_HTML
    assert "overflow:hidden" in RESULTS_HTML


def test_results_routes_are_server_owned_not_browser_timed() -> None:
    assert "fetch(`/api/results/${path}`" in DIRECTOR_HTML
    assert "resultsAction('start'" in DIRECTOR_HTML
    assert "setInterval(loadResultsStatus,1000)" in DIRECTOR_HTML
    assert "setInterval(()=>resultsAction" not in DIRECTOR_HTML
