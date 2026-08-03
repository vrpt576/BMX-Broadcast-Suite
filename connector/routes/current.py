"""Manual current-moto controls and operator/overlay pages."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from connector.dependencies import (
    get_current_moto_service,
    get_race_program_service,
    get_results_roll_service,
)
from connector.models import (
    ActiveGraphic,
    CurrentMoto,
    CurrentMotoUpdate,
    RacePhase,
    RaceProgram,
)
from connector.services.current_moto_service import (
    CurrentMotoService,
    CurrentMotoValidationError,
)
from connector.services.race_program_service import RaceProgramService
from connector.services.race_program_service import RaceSlotUnavailableError
from connector.services.results_roll_service import ResultsRollService

router = APIRouter(tags=["broadcast control"])


@router.get("/current", response_model=CurrentMoto)
def get_current_moto(
    service: CurrentMotoService = Depends(get_current_moto_service),
) -> CurrentMoto:
    return service.get()


@router.get("/current/program", response_model=RaceProgram)
def get_current_program(
    service: RaceProgramService = Depends(get_race_program_service),
) -> RaceProgram:
    try:
        return service.get_program()
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/current", response_model=CurrentMoto)
def set_current_moto(
    update: CurrentMotoUpdate,
    service: CurrentMotoService = Depends(get_current_moto_service),
    programs: RaceProgramService = Depends(get_race_program_service),
) -> CurrentMoto:
    try:
        return programs.select_moto(update)
    except (CurrentMotoValidationError, RaceSlotUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/current/next", response_model=CurrentMoto)
def next_moto(
    programs: RaceProgramService = Depends(get_race_program_service),
) -> CurrentMoto:
    return programs.step_moto(1)


@router.post("/current/previous", response_model=CurrentMoto)
def previous_moto(
    programs: RaceProgramService = Depends(get_race_program_service),
) -> CurrentMoto:
    return programs.step_moto(-1)


@router.get("/current/phases", response_model=list[RacePhase])
def available_phases(
    service: RaceProgramService = Depends(get_race_program_service),
) -> list[RacePhase]:
    return service.available_phases()


@router.post("/current/phase/next", response_model=CurrentMoto)
def next_phase(
    service: RaceProgramService = Depends(get_race_program_service),
) -> CurrentMoto:
    try:
        return service.step_phase(1)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/current/phase/previous", response_model=CurrentMoto)
def previous_phase(
    service: RaceProgramService = Depends(get_race_program_service),
) -> CurrentMoto:
    try:
        return service.step_phase(-1)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/current/phase/select/{phase}", response_model=CurrentMoto)
def select_phase(
    phase: RacePhase,
    service: RaceProgramService = Depends(get_race_program_service),
) -> CurrentMoto:
    try:
        return service.select_phase(phase)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/current/phase/first", response_model=CurrentMoto)
def first_moto_in_phase(
    service: RaceProgramService = Depends(get_race_program_service),
) -> CurrentMoto:
    return service.select_phase_boundary(last=False)


@router.post("/current/phase/last", response_model=CurrentMoto)
def last_moto_in_phase(
    service: RaceProgramService = Depends(get_race_program_service),
) -> CurrentMoto:
    return service.select_phase_boundary(last=True)


@router.post("/current/graphic/{graphic}", response_model=CurrentMoto)
def select_graphic(
    graphic: ActiveGraphic,
    service: CurrentMotoService = Depends(get_current_moto_service),
    results_roll: ResultsRollService = Depends(get_results_roll_service),
) -> CurrentMoto:
    if graphic != ActiveGraphic.RESULTS:
        results_roll.pause_if_active()
    return service.set_graphic(graphic)


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
    .phase { color: #f3b61f; font-size: clamp(1.7rem, 4vw, 3rem); font-weight: 900; letter-spacing: .08em; text-transform: var(--text-transform); }
    .class-name { min-height: 1.5em; margin-top: .25rem; font-size: clamp(1.4rem, 3vw, 2.2rem); font-weight: 800; }
    .moto { font-size: clamp(6rem, 22vw, 12rem); line-height: .95; font-weight: 900; }
    .buttons, .phase-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0; }
    button, input, select { font: inherit; font-size: 1.1rem; padding: .9rem; border-radius: .7rem; border: 1px solid #52606d; }
    button { cursor: pointer; font-weight: 700; }
    .settings { display: grid; grid-template-columns: 1.1fr 1.3fr 1fr 1fr auto; gap: .75rem; align-items: end; }
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
  <div id="class-name-display" class="class-name">Class not set</div>
  <div id="moto" class="moto">1</div>
  <div class="buttons">
    <button id="previous">◀ Previous Moto</button>
    <button id="next">Next Moto ▶</button>
  </div>
  <div class="phase-buttons">
    <button id="previous-phase">◀ Previous Round</button>
    <button id="next-phase">Next Round ▶</button>
  </div>
  <div class="phase-buttons">
    <button id="first-moto">First Moto in Round</button>
    <button id="last-moto">Last Moto in Round</button>
  </div>
  <div class="settings">
    <label>Race round
      <select id="race-phase"><option value="round_1">Round 1</option></select>
    </label>
    <label>Class name<input id="class-name" type="text" maxlength="100" placeholder="17-20 Expert"></label>
    <label>Jump to moto<input id="jump" type="number" min="1" inputmode="numeric"></label>
    <label>Last moto (optional)<input id="maximum" type="number" min="1" inputmode="numeric"></label>
    <button id="apply">Apply</button>
  </div>
  <div id="status" class="status" role="status"></div>
</main>
<script>
const phaseLabels = {
  round_1: 'Round 1', round_2: 'Round 2', round_3: 'Round 3',
  quarterfinal: 'Quarterfinals', semifinal: 'Semifinals', main: 'Main', overall: 'Overall'
};
const moto = document.querySelector('#moto');
const phase = document.querySelector('#phase');
const classNameDisplay = document.querySelector('#class-name-display');
const phaseSelect = document.querySelector('#race-phase');
const className = document.querySelector('#class-name');
const jump = document.querySelector('#jump');
const maximum = document.querySelector('#maximum');
const statusBox = document.querySelector('#status');
let currentState = null;
let mutationVersion = 0;

function render(value) {
  currentState = value;
  moto.textContent = value.moto_number;
  phase.textContent = value.phase_label || phaseLabels[value.race_phase] || value.race_phase;
  classNameDisplay.textContent = value.class_name || 'Class not set';
  phaseSelect.value = value.race_phase;
  className.value = value.class_name || '';
  jump.value = value.moto_number;
  maximum.value = value.maximum_moto ?? '';
  statusBox.textContent = `${value.phase_label || phaseLabels[value.race_phase]} · Moto ${value.moto_number}${value.maximum_moto ? ` of ${value.maximum_moto}` : ''}`;
}
async function loadProgram() {
  try {
    const expectedVersion = mutationVersion;
    const response = await fetch('/api/current/phases', {cache: 'no-store'});
    if (!response.ok) throw new Error();
    const phases = await response.json();
    if (expectedVersion !== mutationVersion) return;
    phaseSelect.replaceChildren();
    for (const item of phases) {
      const option = document.createElement('option');
      option.value = item;
      option.textContent = phaseLabels[item] || item;
      phaseSelect.append(option);
    }
    if (currentState) phaseSelect.value = currentState.race_phase;
  } catch (_) {
    if (!phaseSelect.options.length) {
      phaseSelect.add(new Option('Round 1', 'round_1'));
    }
  }
}
async function request(path, options = {}) {
  const requestVersion = ++mutationVersion;
  statusBox.textContent = 'Updating…';
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  const value = await response.json();
  if (requestVersion !== mutationVersion) return value;
  render(value);
  await loadProgram();
  return value;
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
  const rawMoto = jump.value.trim();
  if (!/^\d+$/.test(rawMoto) || Number(rawMoto) < 1) {
    statusBox.textContent = 'Enter a positive whole-number moto.';
    return;
  }
  const body = { moto_number: Number(rawMoto), race_phase: phaseSelect.value, minimum_moto: 1 };
  if (className.value.trim()) body.class_name = className.value;
  if (maximum.value !== '') body.maximum_moto = Number(maximum.value);
  try { await request('/api/current', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}); }
  catch (error) { statusBox.textContent = error.message; }
}

document.querySelector('#previous').addEventListener('click', () => step('previous'));
document.querySelector('#next').addEventListener('click', () => step('next'));
document.querySelector('#previous-phase').addEventListener('click', () => stepPhase('previous'));
document.querySelector('#next-phase').addEventListener('click', () => stepPhase('next'));
document.querySelector('#first-moto').addEventListener('click', () => request('/api/current/phase/first', {method: 'POST'}).catch(error => statusBox.textContent = error.message));
document.querySelector('#last-moto').addEventListener('click', () => request('/api/current/phase/last', {method: 'POST'}).catch(error => statusBox.textContent = error.message));
document.querySelector('#apply').addEventListener('click', apply);
phaseSelect.addEventListener('change', async () => {
  try { await request(`/api/current/phase/select/${phaseSelect.value}`, {method: 'POST'}); }
  catch (error) { statusBox.textContent = error.message; }
});
jump.addEventListener('keydown', event => { if (event.key === 'Enter') apply(); });
className.addEventListener('keydown', event => { if (event.key === 'Enter') apply(); });
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
    :root { --primary:#f3b61f; --primary-text:#101820; --secondary:#d98b13; --secondary-text:#101820; --panel:#111820; --panel-alt:#1b2733; --panel-text:#fff; --header-panel:#111820; --divider:rgba(255,255,255,.18); --shadow:rgba(0,0,0,.65); --font-family:Arial, Helvetica, sans-serif; --text-transform:uppercase; }
    body { display: grid; place-items: center; font-family: var(--font-family); }
    .stack { display: grid; justify-items: start; filter: drop-shadow(0 4px 7px var(--shadow)); }
    .topline { display: flex; align-items: stretch; }
    .phase { background: var(--primary); color: var(--primary-text); padding: .16em .58em; font-size: 28px; font-weight: 900; letter-spacing: .08em; text-transform: var(--text-transform); }
    .class-name { max-width: 620px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; background: color-mix(in srgb, var(--header-panel) 94%, transparent); color: var(--panel-text); padding: .18em .58em; font-size: 28px; font-weight: 800; }
    .bug { display: flex; align-items: stretch; }
    .label { background: var(--panel-alt); color: var(--panel-text); padding: .28em .52em; font-size: 42px; font-weight: 800; letter-spacing: .04em; }
    .number { min-width: 1.65em; text-align: center; background: var(--primary); color: var(--primary-text); padding: .16em .32em; font-size: 56px; line-height: 1; font-weight: 950; }
  </style>
</head>
<body>
  <div class="stack">
    <div class="topline"><div id="phase" class="phase">ROUND 1</div><div id="class-name" class="class-name">CLASS NOT SET</div></div>
    <div class="bug"><div class="label">CURRENT MOTO</div><div id="number" class="number">1</div></div>
  </div>
<script>
const phaseLabels = {
  round_1: 'ROUND 1', round_2: 'ROUND 2', round_3: 'ROUND 3',
  quarterfinal: 'QUARTERFINALS', semifinal: 'SEMIFINALS', main: 'MAIN', overall: 'OVERALL'
};
const params = new URLSearchParams(location.search);
let themeName = (params.get('theme') || '').toLowerCase();
const preview = ['1','true','yes'].includes((params.get('preview') || '').toLowerCase());
const number = document.querySelector('#number');
const phase = document.querySelector('#phase');
const className = document.querySelector('#class-name');

async function applyTheme() {
  try {
    if (!themeName) { const cfg = await fetch('/api/configuration/public',{cache:'no-store'}); if (cfg.ok) themeName = ((await cfg.json()).default_theme || 'default').toLowerCase(); }
    if (!themeName) themeName='default';
    const response = await fetch(`/api/themes/${encodeURIComponent(themeName)}`, {cache:'no-store'});
    if (!response.ok) return;
    const theme = await response.json();
    const root = document.documentElement.style;
    const c = theme.colors || {};
    const t = theme.typography || {};
    if (c.primary) root.setProperty('--primary', c.primary);
    if (c.primary_text) root.setProperty('--primary-text', c.primary_text);
    if (c.secondary) root.setProperty('--secondary', c.secondary);
    if (c.secondary_text) root.setProperty('--secondary-text', c.secondary_text);
    if (c.panel) root.setProperty('--panel', c.panel);
    if (c.panel_alt) root.setProperty('--panel-alt', c.panel_alt);
    if (c.panel_text) root.setProperty('--panel-text', c.panel_text);
    if (c.header_panel) root.setProperty('--header-panel', c.header_panel);
    if (c.divider) root.setProperty('--divider', c.divider);
    if (c.shadow) root.setProperty('--shadow', c.shadow);
    if (t.font_family) root.setProperty('--font-family', t.font_family);
    if (t.text_transform) root.setProperty('--text-transform', t.text_transform);
  } catch (_) {}
}

async function refresh() {
  try {
    const response = await fetch('/api/current', {cache: 'no-store'});
    if (response.ok) {
      const state = await response.json();
      number.textContent = state.moto_number;
      phase.textContent = state.phase_label || phaseLabels[state.race_phase] || state.race_phase;
      className.textContent = (state.class_name || 'CLASS NOT SET').toUpperCase();
      document.body.style.visibility = (preview || state.active_graphic === 'current_moto') ? 'visible' : 'hidden';
    }
  } catch (_) {}
}
applyTheme();
refresh();
let ws;
function connectSocket(){
  const scheme=location.protocol==='https:'?'wss':'ws';
  ws=new WebSocket(`${scheme}://${location.host}/ws/broadcast`);
  ws.onmessage=e=>{const payload=JSON.parse(e.data);if(payload.current){const state=payload.current;document.querySelector('#phase').textContent=state.phase_label||phaseLabels[state.race_phase]||state.race_phase;document.querySelector('#class-name').textContent=(state.class_name||'CLASS NOT SET').toUpperCase();document.querySelector('#number').textContent=state.moto_number;document.body.style.visibility=(preview||state.active_graphic==='current_moto')?'visible':'hidden';}};
  ws.onclose=()=>setTimeout(connectSocket,1500);
}
connectSocket();
setInterval(refresh, 5000);
</script>
</body>
</html>'''
