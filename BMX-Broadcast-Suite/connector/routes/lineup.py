"""Current rider/gate assignment API and OBS overlay."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from connector.dependencies import get_current_lineup_service
from connector.models import CurrentLineup
from connector.services.current_lineup_service import CurrentLineupService

router = APIRouter(tags=["lineup"])


@router.get("/lineup/current", response_model=CurrentLineup)
def current_lineup(
    demo: bool = Query(False, description="Use bundled 2026-07-23 sample data."),
    motoboard_id: UUID | None = Query(None),
    service: CurrentLineupService = Depends(get_current_lineup_service),
) -> CurrentLineup:
    return service.get(demo=demo, motoboard_id=motoboard_id)


def rider_lineup_overlay() -> str:
    return LINEUP_OVERLAY_HTML


LINEUP_OVERLAY_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BBS Rider Lineup Overlay</title>
  <style>
    :root { --primary:#f3b61f; --primary-text:#101820; --panel:#101820; --panel-text:#fff; --muted-text:#d8dde3; --divider:rgba(255,255,255,.18); --shadow:rgba(0,0,0,.45); --font-family:Arial, Helvetica, sans-serif; --text-transform:uppercase; font-family:var(--font-family); color:var(--panel-text); }
    * { box-sizing: border-box; }
    body { margin: 0; width: 100vw; height: 100vh; overflow: hidden; background: transparent; }
    .wrap { position: absolute; left: 4vw; bottom: 5vh; width: min(900px, 92vw); filter: drop-shadow(0 6px 12px var(--shadow)); }
    .header { display: flex; align-items: stretch; width: fit-content; max-width: 100%; }
    .round { background: var(--primary); color: var(--primary-text); padding: .32em .7em; font-size: 27px; font-weight: 950; letter-spacing: .05em; text-transform: var(--text-transform); }
    .class { background: var(--panel); padding: .32em .75em; font-size: 27px; font-weight: 900; text-transform: var(--text-transform); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .moto { background: var(--primary); color: var(--primary-text); padding: .32em .65em; font-size: 27px; font-weight: 950; white-space: nowrap; }
    .riders { width: min(760px, 88vw); background: color-mix(in srgb, var(--panel) 96%, transparent); border-top: 4px solid var(--primary); }
    .columns { display:grid; grid-template-columns:78px 150px 1fr; align-items:center; min-height:34px; background:color-mix(in srgb, var(--panel) 88%, white 12%); color:var(--muted-text); font-size:15px; font-weight:900; letter-spacing:.08em; text-transform:var(--text-transform); border-bottom:1px solid var(--divider); }
    .columns div { padding:0 .7em; }
    .columns .lane-label, .columns .plate-label { text-align:center; }
    .rider { display: grid; grid-template-columns: 78px 150px 1fr; align-items: center; min-height: 58px; border-bottom: 1px solid var(--divider); }
    .rider:last-child { border-bottom: 0; }
    .gate { align-self: stretch; display: grid; place-items: center; background: var(--primary); color: var(--primary-text); font-size: 32px; font-weight: 950; }
    .bike { padding: 0 .7em; color: var(--primary); font-size: 27px; font-weight: 900; text-align: center; }
    .name { padding: .3em .8em .3em .2em; font-size: 28px; font-weight: 850; text-transform: var(--text-transform); letter-spacing: .02em; }
    .empty { padding: 1.2em; font-size: 24px; font-weight: 700; }
    .offline { display: none; background: color-mix(in srgb, var(--panel) 94%, transparent); color: var(--panel-text); padding: .7em 1em; font-size: 22px; font-weight: 800; width: fit-content; }
  </style>
</head>
<body>
  <section class="wrap" aria-live="polite">
    <div id="graphic">
      <div class="header">
        <div id="round" class="round">ROUND 1</div>
        <div id="class" class="class">7 INTERMEDIATE</div>
        <div id="moto" class="moto">MOTO 1</div>
      </div>
      <div class="riders"><div class="columns"><div class="lane-label">Lane</div><div class="plate-label">Plate Number</div><div>Rider</div></div><div id="riders"></div></div>
    </div>
    <div id="offline" class="offline">LINEUP DATA UNAVAILABLE</div>
  </section>
<script>
const phaseLabels = {
  round_1: 'ROUND 1', round_2: 'ROUND 2', round_3: 'ROUND 3',
  quarterfinal: 'QUARTERFINALS', semifinal: 'SEMIFINALS', main: 'MAINS'
};
const params = new URLSearchParams(location.search);
const demo = ['1', 'true', 'yes'].includes((params.get('demo') || '').toLowerCase());
let themeName = (params.get('theme') || '').toLowerCase();
const preview = ['1', 'true', 'yes'].includes((params.get('preview') || '').toLowerCase());
const endpoint = `/api/lineup/current${demo ? '?demo=true' : ''}`;
const graphic = document.querySelector('#graphic');
const offline = document.querySelector('#offline');
const ridersBox = document.querySelector('#riders');


async function applyTheme() {
  try {
    if (!themeName) { const cfg = await fetch('/api/configuration',{cache:'no-store'}); if (cfg.ok) themeName = ((await cfg.json()).default_theme || 'default').toLowerCase(); }
    if (!themeName) themeName='default';
    const response = await fetch(`/api/themes/${encodeURIComponent(themeName)}`, {cache:'no-store'});
    if (!response.ok) return;
    const theme = await response.json();
    const root = document.documentElement.style;
    const c = theme.colors || {};
    const t = theme.typography || {};
    if (c.primary) root.setProperty('--primary', c.primary);
    if (c.primary_text) root.setProperty('--primary-text', c.primary_text);
    if (c.panel) root.setProperty('--panel', c.panel);
    if (c.panel_text) root.setProperty('--panel-text', c.panel_text);
    if (c.muted_text) root.setProperty('--muted-text', c.muted_text);
    if (c.divider) root.setProperty('--divider', c.divider);
    if (c.shadow) root.setProperty('--shadow', c.shadow);
    if (t.font_family) root.setProperty('--font-family', t.font_family);
    if (t.text_transform) root.setProperty('--text-transform', t.text_transform);
  } catch (_) {}
}

function render(state) {
  document.querySelector('#round').textContent = phaseLabels[state.race_phase] || state.race_phase;
  document.querySelector('#class').textContent = (state.class_name || 'CLASS NOT SET').toUpperCase();
  document.querySelector('#moto').textContent = `MOTO ${state.moto_number}`;
  ridersBox.replaceChildren();
  if (!state.riders.length) {
    const row = document.createElement('div');
    row.className = 'empty';
    row.textContent = 'NO RIDERS ASSIGNED';
    ridersBox.append(row);
  }
  for (const rider of state.riders) {
    const row = document.createElement('div'); row.className = 'rider';
    const gate = document.createElement('div'); gate.className = 'gate'; gate.textContent = rider.gate ?? '—';
    const bike = document.createElement('div'); bike.className = 'bike'; bike.textContent = rider.bike_number ?? '—';
    const name = document.createElement('div'); name.className = 'name';
    name.textContent = `${rider.first_name} ${rider.nickname ? `“${rider.nickname}” ` : ''}${rider.last_name}`;
    row.append(gate, bike, name); ridersBox.append(row);
  }
  graphic.style.display = '';
  offline.style.display = 'none';
  graphic.style.opacity = state.is_stale ? '0.92' : '1';
}
async function refresh() {
  try {
    const [lineupResponse, currentResponse] = await Promise.all([
      fetch(endpoint, {cache: 'no-store'}),
      fetch('/api/current', {cache: 'no-store'})
    ]);
    if (!lineupResponse.ok || !currentResponse.ok) throw new Error('unavailable');
    const [lineupState, currentState] = await Promise.all([lineupResponse.json(), currentResponse.json()]);
    document.body.style.visibility = (preview || currentState.active_graphic === 'lineup') ? 'visible' : 'hidden';
    render(lineupState);
  } catch (_) {
    if (!demo) { offline.textContent='WAITING FOR FIRST VALID LINEUP'; offline.style.display='block'; }
  }
}
applyTheme();
refresh();
function connectSocket(){
  const scheme=location.protocol==='https:'?'wss':'ws';
  const ws=new WebSocket(`${scheme}://${location.host}/ws/broadcast${demo?'?demo=true':''}`);
  ws.onmessage=e=>{const payload=JSON.parse(e.data);if(payload.current)document.body.style.visibility=(preview||payload.current.active_graphic==='lineup')?'visible':'hidden';if(payload.lineup)render(payload.lineup);};
  ws.onclose=()=>setTimeout(connectSocket,1500);
}
connectSocket();
setInterval(refresh,5000);
</script>
</body>
</html>'''
