"""Browser-facing regression checks for Director moto navigation."""

from connector.routes.director import DIRECTOR_HTML


def test_director_next_moto_posts_to_phase_aware_endpoint() -> None:
    assert "$('#next').addEventListener('click',()=>step('next'))" in DIRECTOR_HTML
    assert "request(`/api/current/${direction}`,{method:'POST'})" in DIRECTOR_HTML


def test_director_renders_step_response_before_background_refreshes() -> None:
    response_read = DIRECTOR_HTML.index("const value=await response.json();")
    immediate_render = DIRECTOR_HTML.index("render(value);", response_read)
    program_refresh = DIRECTOR_HTML.index("await loadProgram();", immediate_render)
    lineup_refresh = DIRECTOR_HTML.index("await refreshLineup();", program_refresh)

    assert response_read < immediate_render < program_refresh < lineup_refresh


def test_director_polling_only_reads_and_renders_current_state() -> None:
    polling = (
        "setInterval(()=>fetch('/api/current',{cache:'no-store'})"
        ".then(response=>response.json()).then(render).catch(()=>{}),1000);"
    )
    assert polling in DIRECTOR_HTML


def test_director_event_selection_keeps_the_selected_motoboard_pinned() -> None:
    assert "const boardId=$('#event-select').value||null;" in DIRECTOR_HTML
    assert "motoboard_id:boardId" in DIRECTOR_HTML
    assert "motoboard_id:state?state.motoboard_id:null" in DIRECTOR_HTML
