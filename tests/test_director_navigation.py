"""Browser-facing regression checks for Director moto navigation."""

from connector.routes.director import DIRECTOR_HTML


def test_director_next_moto_posts_to_phase_aware_endpoint() -> None:
    assert "$('#next').addEventListener('click',()=>step('next'))" in DIRECTOR_HTML
    assert "request(`/api/current/${direction}`,{method:'POST'})" in DIRECTOR_HTML


def test_director_renders_step_response_before_background_refreshes() -> None:
    response_read = DIRECTOR_HTML.index("const value=await response.json();")
    immediate_render = DIRECTOR_HTML.index("render(value);", response_read)
    program_refresh = DIRECTOR_HTML.index("await loadProgram(requestVersion);", immediate_render)
    lineup_refresh = DIRECTOR_HTML.index(
        "await refreshLineup(requestVersion);", program_refresh
    )

    assert response_read < immediate_render < program_refresh < lineup_refresh


def test_director_polling_only_reads_and_renders_current_state() -> None:
    assert "fetch('/api/current',{cache:'no-store'})" in DIRECTOR_HTML
    assert ".then(value=>{if(requestVersion===mutationVersion)render(value)})" in DIRECTOR_HTML
    assert "const requestVersion=mutationVersion;" in DIRECTOR_HTML


def test_director_event_selection_keeps_the_selected_motoboard_pinned() -> None:
    assert "const boardId=$('#event-select').value||null;" in DIRECTOR_HTML
    assert "motoboard_id:boardId" in DIRECTOR_HTML
    assert "motoboard_id:state?state.motoboard_id:null" in DIRECTOR_HTML


def test_director_go_to_moto_uses_selected_phase_and_validates_input() -> None:
    assert "const rawMoto=$('#jump').value.trim();" in DIRECTOR_HTML
    assert "!/^\\d+$/.test(rawMoto)||Number(rawMoto)<1" in DIRECTOR_HTML
    assert "moto_number:Number(rawMoto)" in DIRECTOR_HTML
    assert "race_phase:$('#race-phase').value" in DIRECTOR_HTML
    apply_block = DIRECTOR_HTML[
        DIRECTOR_HTML.index("async function apply()") :
        DIRECTOR_HTML.index("async function refreshLineup(")
    ]
    assert "race_phase:'round_1'" not in apply_block


def test_director_uses_global_phase_catalog_and_round_boundaries() -> None:
    assert "fetchWithTimeout('/api/current/phases'" in DIRECTOR_HTML
    assert 'id="first-moto"' in DIRECTOR_HTML
    assert 'id="last-moto"' in DIRECTOR_HTML
    assert "request('/api/current/phase/first',{method:'POST'})" in DIRECTOR_HTML
    assert "request('/api/current/phase/last',{method:'POST'})" in DIRECTOR_HTML


def test_director_round_selector_has_program_segments_but_no_overall() -> None:
    assert '<option value="main">Mains</option>' in DIRECTOR_HTML
    assert "main:'Main'" in DIRECTOR_HTML
    assert 'value="overall"' not in DIRECTOR_HTML
    assert "overall:'Overall'" not in DIRECTOR_HTML


def test_director_ignores_stale_mutation_and_lineup_responses() -> None:
    assert "let mutationVersion=0;" in DIRECTOR_HTML
    assert "const requestVersion=++mutationVersion;" in DIRECTOR_HTML
    assert "if(requestVersion!==mutationVersion)return value;" in DIRECTOR_HTML
    assert "async function refreshLineup(requestVersion=mutationVersion)" in DIRECTOR_HTML
    assert "if(requestVersion!==mutationVersion)return;" in DIRECTOR_HTML


def test_director_renders_actionable_navigation_message() -> None:
    assert "if(value.navigation_message)$('#message').textContent=value.navigation_message;" in DIRECTOR_HTML


def test_director_exposes_event_scoped_main_program_boundary_controls() -> None:
    assert 'id="main-program-start"' in DIRECTOR_HTML
    assert 'id="save-main-program-start"' in DIRECTOR_HTML
    assert 'id="reset-main-program-start"' in DIRECTOR_HTML
    assert "/api/current/main-program-boundary/${boardId}" in DIRECTOR_HTML
    assert "/api/current/main-program-boundary/${boardId}/reset" in DIRECTOR_HTML
    assert "${value.confidence} confidence; not applied" in DIRECTOR_HTML
    assert "(value.evidence||[]).join('; ')" in DIRECTOR_HTML
