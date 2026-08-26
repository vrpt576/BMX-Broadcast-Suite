"""Standalone Sqorz-only overlay: no RaceManager dependency at all.

Reads ONLY the shared SqorzService (see connector/services/sqorz_overlay_service.py).
This module must never import MotoboardService, CurrentMotoService, the race
slot catalog, or anything that queries RaceManager -- that is the entire
point of this overlay: it keeps working when RaceManager is unconfigured or
unreachable.
"""

from fastapi import APIRouter, Depends, Query

from connector.dependencies import get_sqorz_service
from connector.models import SqorzOverlayState
from connector.services.sqorz_overlay_service import build_overlay_state
from connector.services.sqorz_service import SqorzService

router = APIRouter(tags=["sqorz"])


@router.get("/sqorz/current", response_model=SqorzOverlayState)
def sqorz_current(
    class_name: str | None = Query(None, alias="class"),
    phase_code: str | None = Query(None, alias="phase"),
    sqorz: SqorzService = Depends(get_sqorz_service),
) -> SqorzOverlayState:
    return build_overlay_state(sqorz, class_name=class_name, phase_code=phase_code)


def sqorz_timing_overlay() -> str:
    return SQORZ_TIMING_OVERLAY_HTML


SQORZ_TIMING_OVERLAY_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BBS Sqorz Timing Overlay</title>
  <style>
    :root { --primary:#f3b61f; --primary-text:#101820; --panel:#101820; --panel-alt:#1b2733; --panel-text:#fff; --muted-text:#d8dde3; --header-panel:#101820; --row-odd:rgba(16,24,32,.96); --row-even:rgba(27,39,51,.96); --plate:#f3b61f; --divider:rgba(255,255,255,.18); --shadow:rgba(0,0,0,.45); --warning:#7f1d1d; --warning-text:#fff; --font-family:Arial, Helvetica, sans-serif; --text-transform:uppercase; font-family:var(--font-family); color:var(--panel-text); }
    * { box-sizing: border-box; }
    body { margin: 0; width: 100vw; height: 100vh; overflow: hidden; background: transparent; }
    .wrap { position: absolute; left: 4vw; bottom: 5vh; width: min(900px, 92vw); filter: drop-shadow(0 6px 12px var(--shadow)); }
    .header { display: flex; align-items: stretch; width: fit-content; max-width: 100%; }
    .source { background: var(--primary); color: var(--primary-text); padding: .32em .7em; font-size: 20px; font-weight: 950; letter-spacing: .05em; text-transform: var(--text-transform); }
    .class { background: var(--header-panel); padding: .32em .75em; font-size: 27px; font-weight: 900; text-transform: var(--text-transform); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 56vw; }
    .phase { background: var(--primary); color: var(--primary-text); padding: .32em .65em; font-size: 22px; font-weight: 950; white-space: nowrap; text-transform: var(--text-transform); }
    .riders { width: min(760px, 92vw); background: var(--row-odd); border-top: 4px solid var(--primary); }
    .columns { display:grid; grid-template-columns:100px 1fr 150px; align-items:center; min-height:34px; background:var(--panel-alt); color:var(--muted-text); font-size:15px; font-weight:900; letter-spacing:.08em; text-transform:var(--text-transform); border-bottom:1px solid var(--divider); }
    .columns div { padding:0 .7em; }
    .columns .plate-label { text-align:center; }
    .columns .time-label { text-align:right; }
    .rider { display: grid; background:var(--row-odd); grid-template-columns: 100px 1fr 150px; align-items: center; min-height: 60px; border-bottom: 1px solid var(--divider); }
    .rider:nth-child(even) { background:var(--row-even); }
    .rider:last-child { border-bottom: 0; }
    .bike { padding: 0 .7em; color: var(--plate); font-size: 26px; font-weight: 900; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .name { padding: .3em .8em .3em .2em; font-size: 26px; font-weight: 850; text-transform: var(--text-transform); letter-spacing: .02em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .time { padding: 0 .7em; color: var(--plate); font-size: 26px; font-weight: 900; text-align: right; font-variant-numeric: tabular-nums; overflow: hidden; text-overflow: clip; white-space: nowrap; }
    .empty { padding: 1.2em; font-size: 24px; font-weight: 700; }
    .stale { border-top: 3px solid var(--warning); }
    .offline { display: none; background: var(--warning); color: var(--warning-text); padding: .7em 1em; font-size: 22px; font-weight: 800; width: fit-content; }
  </style>
</head>
<body>
  <section class="wrap" aria-live="polite">
    <div id="graphic" style="display:none">
      <div class="header">
        <div class="source">SQORZ LIVE</div>
        <div id="class" class="class">CLASS</div>
        <div id="phase" class="phase">PHASE</div>
      </div>
      <div id="riders-panel" class="riders">
        <div class="columns"><div class="plate-label">Plate</div><div>Rider</div><div class="time-label">Time</div></div>
        <div id="riders"></div>
      </div>
    </div>
    <div id="offline" class="offline">WAITING FOR SQORZ DATA</div>
  </section>
<script>
const params = new URLSearchParams(location.search);
const classFilter = params.get('class') || '';
const phaseFilter = params.get('phase') || '';
let themeName = (params.get('theme') || '').toLowerCase();
const endpoint = `/api/sqorz/current${classFilter || phaseFilter ? '?' : ''}${classFilter ? `class=${encodeURIComponent(classFilter)}` : ''}${classFilter && phaseFilter ? '&' : ''}${phaseFilter ? `phase=${encodeURIComponent(phaseFilter)}` : ''}`;
const graphic = document.querySelector('#graphic');
const offline = document.querySelector('#offline');
const ridersBox = document.querySelector('#riders');
const ridersPanel = document.querySelector('#riders-panel');
let everRendered = false;

async function applyTheme() {
  try {
    if (!themeName) { const cfg = await fetch('/api/configuration/public', {cache:'no-store'}); if (cfg.ok) themeName = ((await cfg.json()).default_theme || 'default').toLowerCase(); }
    if (!themeName) themeName = 'default';
    const response = await fetch(`/api/themes/${encodeURIComponent(themeName)}`, {cache:'no-store'});
    if (!response.ok) return;
    const theme = await response.json();
    const root = document.documentElement.style;
    const c = theme.colors || {};
    const t = theme.typography || {};
    if (c.primary) root.setProperty('--primary', c.primary);
    if (c.primary_text) root.setProperty('--primary-text', c.primary_text);
    if (c.panel) root.setProperty('--panel', c.panel);
    if (c.panel_alt) root.setProperty('--panel-alt', c.panel_alt);
    if (c.panel_text) root.setProperty('--panel-text', c.panel_text);
    if (c.muted_text) root.setProperty('--muted-text', c.muted_text);
    if (c.header_panel) root.setProperty('--header-panel', c.header_panel);
    if (c.row_odd) root.setProperty('--row-odd', c.row_odd);
    if (c.row_even) root.setProperty('--row-even', c.row_even);
    if (c.plate) root.setProperty('--plate', c.plate);
    if (c.divider) root.setProperty('--divider', c.divider);
    if (c.shadow) root.setProperty('--shadow', c.shadow);
    if (c.warning) root.setProperty('--warning', c.warning);
    if (c.warning_text) root.setProperty('--warning-text', c.warning_text);
    if (t.font_family) root.setProperty('--font-family', t.font_family);
    if (t.text_transform) root.setProperty('--text-transform', t.text_transform);
  } catch (_) {}
}

function render(state) {
  if (!state.enabled || !state.race) {
    if (!everRendered) {
      offline.textContent = !state.enabled ? 'SQORZ DISABLED' : 'WAITING FOR SQORZ DATA';
      offline.style.display = 'block';
      graphic.style.display = 'none';
    }
    return;
  }
  everRendered = true;
  const race = state.race;
  document.querySelector('#class').textContent = (race.class_name || 'CLASS').toUpperCase();
  // Sqorz's own phase name is deliberately shown here -- this overlay is
  // Sqorz's own view of the event, not BBS's RaceManager-derived program.
  document.querySelector('#phase').textContent = (race.phase_name || race.phase_code || '').toUpperCase();
  ridersBox.replaceChildren();
  if (!race.riders.length) {
    const row = document.createElement('div');
    row.className = 'empty';
    row.textContent = 'NO RIDERS FOR THIS RACE';
    ridersBox.append(row);
  }
  for (const rider of race.riders) {
    const row = document.createElement('div'); row.className = 'rider';
    const bike = document.createElement('div'); bike.className = 'bike'; bike.textContent = rider.plate ?? '—';
    const name = document.createElement('div'); name.className = 'name';
    name.textContent = `${rider.first_name || ''} ${rider.last_name || ''}`.trim() || 'UNKNOWN';
    const time = document.createElement('div'); time.className = 'time';
    time.textContent = (rider.time_seconds === null || rider.time_seconds === undefined) ? '' : rider.time_seconds.toFixed(3);
    row.append(bike, name, time); ridersBox.append(row);
  }
  graphic.style.display = '';
  offline.style.display = 'none';
  ridersPanel.classList.toggle('stale', !!state.stale);
  graphic.style.opacity = state.stale ? '0.9' : (state.reachable ? '1' : '0.9');
}

async function refresh() {
  try {
    const response = await fetch(endpoint, {cache: 'no-store'});
    if (!response.ok) throw new Error('unavailable');
    render(await response.json());
  } catch (_) {
    // One failed fetch never blanks an already-rendered screen -- keep
    // showing the last-known-good race until the next successful poll.
  }
}
applyTheme();
refresh();
// Refreshed independently of the server-side Sqorz poll interval
// (BBS_SQORZ_POLL_SECONDS) -- SqorzService already throttles the actual
// upstream fetch, so polling this endpoint more often than that is free;
// it just re-reads the same in-memory cache until a real fetch is due.
setInterval(refresh, 2000);
</script>
</body>
</html>'''
