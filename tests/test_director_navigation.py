"""Browser-facing regression checks for Director moto navigation."""

from connector.routes.director import DIRECTOR_HTML


def block(start: str, end: str) -> str:
    return DIRECTOR_HTML[DIRECTOR_HTML.index(start) : DIRECTOR_HTML.index(end)]


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
    assert "const rawMoto=(jumpDraft??field.value).trim();" in DIRECTOR_HTML
    assert "!/^\\d+$/.test(rawMoto)||Number(rawMoto)<1" in DIRECTOR_HTML
    assert "moto_number:Number(rawMoto)" in DIRECTOR_HTML
    assert "race_phase:$('#race-phase').value" in DIRECTOR_HTML
    apply_block = DIRECTOR_HTML[
        DIRECTOR_HTML.index("async function apply()") :
        DIRECTOR_HTML.index("async function refreshLineup(")
    ]
    assert "race_phase:'round_1'" not in apply_block


def test_director_preserves_pending_jump_during_status_refresh_and_applies_it() -> None:
    """Current 5 -> draft 27 -> poll 5 -> submit 27 -> confirmed 27."""
    render_block = block("function render(value)", "async function loadEvents()")
    apply_block = block("async function apply()", "async function refreshLineup(")

    assert render_block.index("captureJumpDraft();") < render_block.index(
        "syncJumpInput(value.moto_number);"
    )
    assert "$('#jump').value=value.moto_number;" not in render_block
    assert "if(jumpDirty||document.activeElement===field)" in DIRECTOR_HTML
    assert "const rawMoto=(jumpDraft??field.value).trim();" in apply_block
    assert "moto_number:Number(rawMoto)" in apply_block
    assert "const confirmed=await request('/api/current'" in apply_block
    assert apply_block.index("const confirmed=await request('/api/current'") < apply_block.index(
        "mutationVersion++;"
    ) < apply_block.index(
        "jumpDirty=false;"
    )
    assert "currentField.value=confirmed.moto_number;" in apply_block


def test_director_invalidates_overlapping_poll_after_successful_jump() -> None:
    apply_block = block("async function apply()", "async function refreshLineup(")
    poll_block = block("setInterval(()=>{", "setInterval(loadProgram,5000);")

    assert "const requestVersion=mutationVersion;" in poll_block
    assert "if(requestVersion===mutationVersion)render(value)" in poll_block
    assert "mutationVersion++;" in apply_block
    assert apply_block.index("mutationVersion++;") < apply_block.index("jumpDirty=false;")


def test_director_marks_typing_and_spinner_changes_dirty() -> None:
    dirty_block = block("function markJumpDirty(event)", "function renderEventSelection(value)")

    assert "jumpDraft=event.target.value;" in dirty_block
    assert "jumpDirty=true;" in dirty_block
    assert "document.addEventListener('input',markJumpDirty);" in DIRECTOR_HTML
    assert "document.addEventListener('change',markJumpDirty);" in DIRECTOR_HTML


def test_director_jump_draft_survives_dom_replacement_and_apply_failure() -> None:
    apply_block = block("async function apply()", "async function refreshLineup(")

    # Delegated listeners survive replacement, while the draft lives outside the DOM.
    assert "let jumpDraft=null;" in DIRECTOR_HTML
    assert "document.addEventListener('input',markJumpDirty);" in DIRECTOR_HTML
    assert "function restoreJumpDraft()" in DIRECTOR_HTML
    assert "jumpDraft=rawMoto;" in apply_block
    assert "jumpDirty=true;" in apply_block
    assert "restoreJumpDraft();" in apply_block
    assert apply_block.index("restoreJumpDraft();") < apply_block.index(
        "$('#message').textContent=error.message;"
    )


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
