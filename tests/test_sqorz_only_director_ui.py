"""Sqorz-only mode's control mapping on /director: hide vs disable vs
repurpose, per the approved design. All assertions are on DIRECTOR_HTML's
source text (matching this file's existing testing convention -- see
test_director_navigation.py, test_director_confirmation.py) since the
existing RaceManager-mode behavior stays byte-for-byte in place and this
only proves the additive Sqorz-only branch is really wired in, not that it
replaced anything.
"""

from __future__ import annotations

from connector.routes.director import DIRECTOR_HTML


def test_mode_banner_exists_with_a_recheck_button() -> None:
    """Change 1: mode and reason are shown, with an explicit operator-
    triggered Re-check action -- never a timer."""
    assert 'id="mode-banner"' in DIRECTOR_HTML
    assert 'id="mode-value"' in DIRECTOR_HTML
    assert 'id="mode-reason"' in DIRECTOR_HTML
    assert 'id="mode-recheck"' in DIRECTOR_HTML
    assert "setInterval(loadMode" not in DIRECTOR_HTML  # no timer-driven mode swap


def test_recheck_shows_the_decision_before_and_after() -> None:
    assert "fetchWithTimeout('/api/mode/recheck'" in DIRECTOR_HTML
    assert "result.before" in DIRECTOR_HTML
    assert "result.after" in DIRECTOR_HTML
    assert "mode-recheck-detail" in DIRECTOR_HTML


def test_sqorz_nav_panel_and_its_controls_exist() -> None:
    assert 'id="sqorz-nav-panel"' in DIRECTOR_HTML
    assert 'id="sqorz-class-select"' in DIRECTOR_HTML
    assert 'id="sqorz-event-select"' in DIRECTOR_HTML
    assert 'id="sqorz-jump-recent"' in DIRECTOR_HTML
    assert "class=\"sqorz-panel mode-hidden\"" in DIRECTOR_HTML  # hidden by default, shown only in Sqorz-only mode


def test_next_previous_are_repurposed_not_duplicated() -> None:
    """The same #previous/#next buttons dispatch to the Sqorz-only
    endpoints when in that mode -- no separate button pair was added for
    it, per the approved "repurpose" category."""
    assert "if(mode==='sqorz_only'){" in DIRECTOR_HTML
    assert "return sqorzStep(direction);" in DIRECTOR_HTML
    assert "fetchWithTimeout(`/api/sqorz-director/${direction}`" in DIRECTOR_HTML
    # The RaceManager path is untouched underneath the new branch.
    assert "$('#next').addEventListener('click',()=>step('next'))" in DIRECTOR_HTML
    assert "request(`/api/current/${direction}`,{method:'POST'})" in DIRECTOR_HTML


def test_backward_sqorz_navigation_still_goes_through_the_confirm_modal() -> None:
    assert "confirmRaceNavigation('Move backward one race?',()=>sqorzStep(direction))" in DIRECTOR_HTML


def test_racemanager_only_controls_are_marked_hideable_not_removed() -> None:
    """Hidden via a runtime class toggle, not deleted from the page --
    every element's id stays present in source (existing tests already pin
    each of these ids individually; this just confirms the hide mechanism
    targets real markup, not a no-op selector)."""
    for marker in (
        'class="event-picker racemanager-only"',
        'class="event-detail racemanager-only"',
        'class="boundary-control racemanager-only"',
        'class="results-controls racemanager-only"',
    ):
        assert marker in DIRECTOR_HTML
    assert "document.querySelectorAll('.racemanager-only')" in DIRECTOR_HTML


def test_show_current_results_is_disabled_with_a_reason_not_hidden() -> None:
    assert "resultsButton.disabled=sqorzOnly;" in DIRECTOR_HTML
    assert "Results require RaceManager -- not available in Sqorz-only mode." in DIRECTOR_HTML
    # Still present and clickable in markup -- disabled is a runtime state, not removal.
    assert 'id="show-current-results"' in DIRECTOR_HTML


def test_results_roll_cluster_ids_all_still_present_in_source() -> None:
    """Hidden as a whole cluster in Sqorz-only mode, but every control this
    project's own test_results_ui.py already pins must remain in markup."""
    for identifier in (
        "results-start-button", "results-pause", "results-resume",
        "results-previous", "results-next", "results-stop",
        "results-interval", "results-status",
    ):
        assert f'id="{identifier}"' in DIRECTOR_HTML


def test_r_keyboard_shortcut_is_a_no_op_toast_in_sqorz_only_mode() -> None:
    assert "Results are unavailable in Sqorz-only mode." in DIRECTOR_HTML
    r_branch = DIRECTOR_HTML[
        DIRECTOR_HTML.index("event.key.toLowerCase()==='r'") :
        DIRECTOR_HTML.index("event.key.toLowerCase()==='h'")
    ]
    assert "resultsAction('show-current')" in r_branch  # still the real action outside Sqorz-only mode
    assert "mode==='sqorz_only'" in r_branch


def test_round_keyboard_shortcuts_are_disabled_in_sqorz_only_mode() -> None:
    bracket_branch = DIRECTOR_HTML[DIRECTOR_HTML.index("event.key===']')"):]
    assert "mode!=='sqorz_only'" in bracket_branch


def test_graphic_and_break_buttons_are_never_marked_racemanager_only() -> None:
    """Unchanged per the approved control mapping: on-air graphic
    switching is file-backed state (CurrentMotoService), not a RaceManager
    query, so it works identically in every mode."""
    graphics_block = DIRECTOR_HTML[
        DIRECTOR_HTML.index('<div class="graphic-buttons">') :
        DIRECTOR_HTML.index("</div>", DIRECTOR_HTML.index('<div class="graphic-buttons">'))
    ]
    assert "racemanager-only" not in graphics_block


def test_remote_control_token_and_nav_confirm_modal_are_unchanged() -> None:
    assert 'id="remote-control-token"' in DIRECTOR_HTML
    assert 'id="navigation-confirm-modal"' in DIRECTOR_HTML
    assert "racemanager-only" not in DIRECTOR_HTML[
        DIRECTOR_HTML.index('id="remote-control-token"') - 200 : DIRECTOR_HTML.index('id="remote-control-token"')
    ]


def test_sqorz_director_endpoints_are_all_referenced() -> None:
    for path in (
        "/api/sqorz-director/state",
        "/api/sqorz-director/events",
        "/api/sqorz-director/select-class/",
        "/api/sqorz-director/jump-to-recent",
    ):
        assert path in DIRECTOR_HTML


def test_event_switch_reuses_the_existing_configuration_endpoint() -> None:
    """No new write endpoint for switching Sqorz events -- reuses
    /api/configuration like the sqorz_director.py route design intends."""
    assert "sqorz_event_id:eventId" in DIRECTOR_HTML
    assert "fetch('/api/configuration'" in DIRECTOR_HTML
