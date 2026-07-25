"""Manual current-moto controls and operator/overlay pages."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from connector.dependencies import get_current_moto_service
from connector.models import CurrentMoto, CurrentMotoUpdate
from connector.services.current_moto_service import (
    CurrentMotoService,
    CurrentMotoValidationError,
)

router = APIRouter(tags=["broadcast control"])


@router.get("/current", response_model=CurrentMoto)
def get_current_moto(
    service: CurrentMotoService = Depends(get_current_moto_service),
) -> CurrentMoto:
    return service.get()


@router.put("/current", response_model=CurrentMoto)
def set_current_moto(
    update: CurrentMotoUpdate,
    service: CurrentMotoService = Depends(get_current_moto_service),
) -> CurrentMoto:
    try:
        return service.set(update)
    except CurrentMotoValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/current/next", response_model=CurrentMoto)
def next_moto(
    service: CurrentMotoService = Depends(get_current_moto_service),
) -> CurrentMoto:
    return service.next()


@router.post("/current/previous", response_model=CurrentMoto)
def previous_moto(
    service: CurrentMotoService = Depends(get_current_moto_service),
) -> CurrentMoto:
    return service.previous()


@router.post("/current/phase/next", response_model=CurrentMoto)
def next_phase(
    service: CurrentMotoService = Depends(get_current_moto_service),
) -> CurrentMoto:
    return service.next_phase()


@router.post("/current/phase/previous", response_model=CurrentMoto)
def previous_phase(
    service: CurrentMotoService = Depends(get_current_moto_service),
) -> CurrentMoto:
    return service.previous_phase()


@router.post("/current/reset", response_model=CurrentMoto)
def reset_moto(
    service: CurrentMotoService = Depends(get_current_moto_service),
) -> CurrentMoto:
    return service.reset()


def controller_page() -> str:
    return CONTROLLER_HTML


def current_moto_overlay() -> str:
    return OVERLAY_HTML


CONTROLLER_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BBS Moto Controller</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #10141a; }
    main { width: min(820px, 92vw); text-align: center; }
    h1 { margin-bottom: .25rem; }
    .hint { opacity: .75; margin-bottom: 1rem; }
    .phase { color: #f3b61f; font-size: clamp(1.7rem, 4vw, 3rem); font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
    .moto { font-size: clamp(6rem, 22vw, 12rem); line-height: .95; font-weight: 900; }
    .buttons, .phase-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0; }
    button, input, select { font: inherit; font-size: 1.1rem; padding: .9rem; border-radius: .7rem; border: 1px solid #52606d; }
    button { cursor: pointer; font-weight: 700; }
    .settings { display: grid; grid-template-columns: 1.1fr 1fr 1fr auto; gap: .75rem; align-items: end; }
    label { display: grid; gap: .4rem; text-align: left; }
    .status { min-height: 1.5rem; margin-top: 1rem; }
    @media (max-width: 720px) { .settings { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <h1>BBS Race Controller</h1>
  <div class="hint">←/→ moto · [ / ] round · Number + Enter jump</div>
  <div id="phase" class="phase">Round 1</div>
  <div id="moto" class="moto">1</div>
  <div class="buttons">
    <button id="previous">◀ Previous Moto</button>
    <button id="next">Next Moto ▶</button>
  </div>
  <div class="phase-buttons">
    <button id="previous-phase">◀ Previous Round</button>
    <button id="next-phase">Next Round ▶</button>
  </div>
  <div class="settings">
    <label>Race round
      <select id="race-phase">
        <option value="round_1">Round 1</option>
        <option value="round_2">Round 2</option>
        <option value="round_3">Round 3</option>
        <option value="quarterfinal">Quarterfinals</option>
        <option value="semifinal">Semifinals</option>
        <option value="main">Mains</option>
      </select>
    </label>
    <label>Jump to moto<input id="jump" type="number" min="1" inputmode="numeric"></label>
    <label>Last moto (optional)<input id="maximum" type="number" min="1" inputmode="numeric"></label>
    <button id="apply">Apply</button>
  </div>
  <div id="status" class="status" role="status"></div>
</main>
<script>
const phaseLabels = {
  round_1: 'Round 1', round_2: 'Round 2', round_3: 'Round 3',
  quarterfinal: 'Quarterfinals', semifinal: 'Semifinals', main: 'Mains'
};
const moto = document.querySelector('#moto');
const phase = document.querySelector('#phase');
const phaseSelect = document.querySelector('#race-phase');
const jump = document.querySelector('#jump');
const maximum = document.querySelector('#maximum');
const statusBox = document.querySelector('#status');

function render(value) {
  moto.textContent = value.moto_number;
  phase.textContent = phaseLabels[value.race_phase] || value.race_phase;
  phaseSelect.value = value.race_phase;
  jump.value = value.moto_number;
  maximum.value = value.maximum_moto ?? '';
  statusBox.textContent = `${phaseLabels[value.race_phase]} · Moto ${value.moto_number}${value.maximum_moto ? ` of ${value.maximum_moto}` : ''}`;
}
async function request(path, options = {}) {
  statusBox.textContent = 'Updating…';
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  render(await response.json());
}
async function step(direction) {
  try { await request(`/api/current/${direction}`, {method: 'POST'}); }
  catch (error) { statusBox.textContent = error.message; }
}
async function stepPhase(direction) {
  try { await request(`/api/current/phase/${direction}`, {method: 'POST'}); }
  catch (error) { statusBox.textContent = error.message; }
}
async function apply() {
  const body = { moto_number: Number(jump.value), race_phase: phaseSelect.value, minimum_moto: 1 };
  if (maximum.value !== '') body.maximum_moto = Number(maximum.value);
  try { await request('/api/current', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}); }
  catch (error) { statusBox.textContent = error.message; }
}

document.querySelector('#previous').addEventListener('click', () => step('previous'));
document.querySelector('#next').addEventListener('click', () => step('next'));
document.querySelector('#previous-phase').addEventListener('click', () => stepPhase('previous'));
document.querySelector('#next-phase').addEventListener('click', () => stepPhase('next'));
document.querySelector('#apply').addEventListener('click', apply);
jump.addEventListener('keydown', event => { if (event.key === 'Enter') apply(); });
window.addEventListener('keydown', event => {
  if (event.target.tagName === 'INPUT' || event.target.tagName === 'SELECT') return;
  if (['ArrowRight', 'ArrowUp', ' ', 'PageDown'].includes(event.key)) { event.preventDefault(); step('next'); }
  if (['ArrowLeft', 'ArrowDown', 'PageUp'].includes(event.key)) { event.preventDefault(); step('previous'); }
  if (event.key === ']' || event.key === '}') { event.preventDefault(); stepPhase('next'); }
  if (event.key === '[' || event.key === '{') { event.preventDefault(); stepPhase('previous'); }
});
request('/api/current').catch(error => statusBox.textContent = error.message);
</script>
</body>
</html>'''


OVERLAY_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BBS Current Moto Overlay</title>
  <style>
    html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: transparent; }
    body { display: grid; place-items: center; font-family: Arial, Helvetica, sans-serif; }
    .stack { display: grid; justify-items: start; filter: drop-shadow(0 4px 7px rgba(0,0,0,.65)); }
    .phase { background: #f3b61f; color: #101820; padding: .16em .58em; font-size: 28px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
    .bug { display: flex; align-items: stretch; }
    .label { background: #111820; color: white; padding: .28em .52em; font-size: 42px; font-weight: 800; letter-spacing: .04em; }
    .number { min-width: 1.65em; text-align: center; background: #f3b61f; color: #101820; padding: .16em .32em; font-size: 56px; line-height: 1; font-weight: 950; }
  </style>
</head>
<body>
  <div class="stack">
    <div id="phase" class="phase">ROUND 1</div>
    <div class="bug"><div class="label">CURRENT MOTO</div><div id="number" class="number">1</div></div>
  </div>
<script>
const phaseLabels = {
  round_1: 'ROUND 1', round_2: 'ROUND 2', round_3: 'ROUND 3',
  quarterfinal: 'QUARTERFINALS', semifinal: 'SEMIFINALS', main: 'MAINS'
};
const number = document.querySelector('#number');
const phase = document.querySelector('#phase');
async function refresh() {
  try {
    const response = await fetch('/api/current', {cache: 'no-store'});
    if (response.ok) {
      const state = await response.json();
      number.textContent = state.moto_number;
      phase.textContent = phaseLabels[state.race_phase] || state.race_phase;
    }
  } catch (_) {}
}
refresh();
setInterval(refresh, 250);
</script>
</body>
</html>'''
