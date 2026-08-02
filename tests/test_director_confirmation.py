"""Browser-facing coverage for event-scoped navigation confirmation."""

from connector.routes.director import DIRECTOR_HTML


def block(start: str, end: str) -> str:
    return DIRECTOR_HTML[DIRECTOR_HTML.index(start) : DIRECTOR_HTML.index(end)]


def test_navigation_uses_custom_modal_instead_of_browser_confirm() -> None:
    assert 'id="navigation-confirm-modal"' in DIRECTOR_HTML
    assert 'role="dialog"' in DIRECTOR_HTML
    assert "Do not ask again for this event" in DIRECTOR_HTML
    assert "confirm(" not in DIRECTOR_HTML
    assert "confirmRaceNavigation('Move backward one moto?'" in DIRECTOR_HTML
    assert "confirmRaceNavigation('Jump backward to an earlier moto?'" in DIRECTOR_HTML


def test_suppression_is_persisted_by_current_event_identity() -> None:
    assert "state?.motoboard_id||state?.resolved_motoboard_id||null" in DIRECTOR_HTML
    assert "bbs.navigation.confirm.suppressed." in DIRECTOR_HTML
    assert "localStorage.getItem(key)==='true'" in DIRECTOR_HTML
    assert "localStorage.setItem(pending.preferenceKey,'true')" in DIRECTOR_HTML
    assert "updateNavigationPreferenceControl();" in block(
        "function render(value)", "async function loadEvents()"
    )


def test_different_event_uses_a_different_preference_key() -> None:
    key_function = block(
        "function navigationPreferenceKey", "function navigationConfirmationSuppressed"
    )
    assert "eventId=navigationEventId()" in key_function
    assert "`${navigationPreferencePrefix}${eventId}`" in key_function
    assert "'latest'" not in key_function


def test_reset_removes_only_current_event_navigation_preference() -> None:
    reset = block(
        "$('#reset-navigation-confirmation').addEventListener",
        "$('#event-select').addEventListener",
    )
    assert "const key=navigationPreferenceKey();" in reset
    assert "localStorage.removeItem(key)" in reset
    assert "localStorage.clear" not in reset


def test_suppression_does_not_wrap_graphic_results_or_break_actions() -> None:
    graphics = block("async function graphic(name)", "function renderResultsStatus")
    results = block("async function resultsAction", "async function loadResultsStatus")
    breaks = block("async function breakGraphic", "function renderResultsStatus")
    assert "confirmRaceNavigation" not in graphics
    assert "confirmRaceNavigation" not in results
    assert "confirmRaceNavigation" not in breaks
