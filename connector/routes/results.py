"""Official current-results and server-owned Results Roll API."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from connector.dependencies import get_results_roll_service
from connector.models import CurrentResults, ResultsRollStart, ResultsRollState
from connector.services.results_roll_service import (
    ResultsRollService,
    ResultsRollUnavailableError,
)

router = APIRouter(tags=["results"])


@router.get("/results/current", response_model=CurrentResults)
def current_results(
    demo: bool = Query(False),
    service: ResultsRollService = Depends(get_results_roll_service),
) -> CurrentResults:
    return _control(lambda: service.current_result(demo=demo))


@router.get("/results/status", response_model=ResultsRollState)
def results_status(
    service: ResultsRollService = Depends(get_results_roll_service),
) -> ResultsRollState:
    return service.status()


def _control(action):
    try:
        return action()
    except (ResultsRollUnavailableError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/results/show-current", response_model=ResultsRollState)
def show_current_results(
    service: ResultsRollService = Depends(get_results_roll_service),
) -> ResultsRollState:
    return _control(service.show_current)


@router.post("/results/start", response_model=ResultsRollState)
def start_results_roll(
    request: ResultsRollStart,
    service: ResultsRollService = Depends(get_results_roll_service),
) -> ResultsRollState:
    return _control(lambda: service.start(request))


@router.post("/results/pause", response_model=ResultsRollState)
def pause_results_roll(
    service: ResultsRollService = Depends(get_results_roll_service),
) -> ResultsRollState:
    return service.pause()


@router.post("/results/resume", response_model=ResultsRollState)
def resume_results_roll(
    service: ResultsRollService = Depends(get_results_roll_service),
) -> ResultsRollState:
    return _control(service.resume)


@router.post("/results/previous", response_model=ResultsRollState)
def previous_result(
    service: ResultsRollService = Depends(get_results_roll_service),
) -> ResultsRollState:
    return _control(service.previous)


@router.post("/results/next", response_model=ResultsRollState)
def next_result(
    service: ResultsRollService = Depends(get_results_roll_service),
) -> ResultsRollState:
    return _control(service.next)


@router.post("/results/stop", response_model=ResultsRollState)
def stop_results_roll(
    service: ResultsRollService = Depends(get_results_roll_service),
) -> ResultsRollState:
    return service.stop()


def results_overlay() -> str:
    return RESULTS_HTML


RESULTS_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BBS Official Results</title><style>
:root{--primary:#f3b61f;--primary-text:#101820;--panel:#101820;--panel-alt:#1b2733;--panel-text:#fff;--header-panel:#101820;--row-odd:rgba(16,24,32,.97);--row-even:rgba(27,39,51,.97);--plate:#f3b61f;--divider:rgba(255,255,255,.18);--shadow:rgba(0,0,0,.55);--warning:#7f1d1d;--warning-text:#fff;--font-family:Arial,sans-serif;--text-transform:uppercase;font-family:var(--font-family)}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent;color:var(--panel-text)}
.wrap{position:absolute;left:5vw;bottom:5vh;width:min(1100px,90vw);filter:drop-shadow(0 8px 18px var(--shadow))}.event{font-size:18px;font-weight:800;letter-spacing:.08em;text-transform:var(--text-transform);padding:9px 16px;background:var(--panel-alt);width:max-content;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.head{display:grid;grid-template-columns:auto 1fr auto;align-items:stretch}.title{background:var(--primary);color:var(--primary-text);font-size:36px;font-weight:950;padding:12px 18px;white-space:nowrap}.class{background:var(--header-panel);font-size:30px;font-weight:900;padding:15px 20px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.progress{background:var(--panel-alt);font-size:21px;font-weight:850;padding:19px 18px;white-space:nowrap}.phase{border-top:4px solid var(--primary);background:var(--panel-alt);padding:7px 16px;font-size:18px;font-weight:850;letter-spacing:.06em}.rows{background:var(--panel)}.row{display:grid;grid-template-columns:90px 155px 1fr 180px;min-height:64px;align-items:center;border-bottom:1px solid var(--divider);font-size:25px;font-weight:800;background:var(--row-odd)}.row:nth-child(even){background:var(--row-even)}.place{height:100%;display:grid;place-items:center;background:var(--primary);color:var(--primary-text);font-size:30px;font-weight:950}.plate{color:var(--plate);text-align:center}.name{text-transform:var(--text-transform)}.rider-meta{margin-top:.12em;color:#d5dde5;font-size:15px;font-weight:700;letter-spacing:.04em;text-transform:none}.status{text-align:right;padding-right:18px;font-size:18px;color:#d5dde5}.notice{display:none;background:var(--warning);color:var(--warning-text);padding:12px 16px;font-weight:900;font-size:20px}.empty{padding:24px;font-size:28px;font-weight:850;text-align:center}
</style></head><body><section class="wrap"><div id="notice" class="notice"></div><div id="graphic"><div id="event" class="event"></div><div class="head"><div id="title" class="title">MOTO 1 RESULTS</div><div id="class" class="class">CLASS</div><div id="progress" class="progress"></div></div><div id="phase" class="phase">OFFICIAL RESULTS</div><div id="rows" class="rows"></div></div></section><script>
const p=new URLSearchParams(location.search),demo=['1','true','yes'].includes((p.get('demo')||'').toLowerCase()),preview=['1','true','yes'].includes((p.get('preview')||'').toLowerCase());let themeName=(p.get('theme')||'').toLowerCase();
async function applyTheme(){try{if(!themeName){const cfg=await fetch('/api/configuration/public',{cache:'no-store'});if(cfg.ok)themeName=((await cfg.json()).default_theme||'default').toLowerCase()}if(!themeName)themeName='default';const response=await fetch(`/api/themes/${encodeURIComponent(themeName)}`,{cache:'no-store'});if(!response.ok)return;const theme=await response.json(),root=document.documentElement.style,c=theme.colors||{},t=theme.typography||{},map={primary:'--primary',primary_text:'--primary-text',panel:'--panel',panel_alt:'--panel-alt',panel_text:'--panel-text',header_panel:'--header-panel',row_odd:'--row-odd',row_even:'--row-even',plate:'--plate',divider:'--divider',shadow:'--shadow',warning:'--warning',warning_text:'--warning-text'};for(const[key,variable]of Object.entries(map))if(c[key])root.setProperty(variable,c[key]);if(t.font_family)root.setProperty('--font-family',t.font_family);if(t.text_transform)root.setProperty('--text-transform',t.text_transform)}catch(_){}}
function metadataText(rider){const values=[];if(Number.isInteger(rider.age))values.push(`Age ${rider.age}`);const track=(rider.home_track||'').trim();if(track)values.push(track);return values.join(' · ')}
function render(s,c){document.body.style.visibility=(preview||c.active_graphic==='results')?'visible':'hidden';document.querySelector('#event').textContent=s.event_name||'';title.textContent=`MOTO ${s.moto_number} RESULTS`;document.querySelector('#class').textContent=s.class_name;progress.textContent=s.progress_index&&s.progress_total?`MOTO ${s.progress_index} OF ${s.progress_total}`:'';phase.textContent=`${(s.phase_label||s.race_phase).toUpperCase()} · ${s.result_status==='official'?'OFFICIAL RESULTS':s.result_status==='incomplete'?'INCOMPLETE RESULTS':'RESULTS UNAVAILABLE'}`;notice.style.display=s.is_stale||s.result_status!=='official'?'block':'none';notice.textContent=s.is_stale?'DATABASE OFFLINE — LAST KNOWN RESULTS':s.result_status==='incomplete'?'RESULTS INCOMPLETE':'RESULTS UNAVAILABLE';rows.replaceChildren();for(const r of s.riders.slice(0,8)){const d=document.createElement('div');d.className='row';const place=document.createElement('div'),plate=document.createElement('div'),name=document.createElement('div'),status=document.createElement('div');place.className='place';plate.className='plate';name.className='name';status.className='status';place.textContent=r.finish??'—';plate.textContent=r.bike_number??'—';const primary=document.createElement('div');primary.textContent=`${r.first_name} ${r.last_name}`;name.append(primary);const metadata=metadataText(r);if(metadata){const subtitle=document.createElement('div');subtitle.className='rider-meta';subtitle.textContent=metadata;name.append(subtitle)}status.textContent=r.status||'';d.append(place,plate,name,status);rows.append(d)}if(!s.riders.length){const d=document.createElement('div');d.className='empty';d.textContent='RESULTS UNAVAILABLE';rows.append(d)}}
async function load(){try{const[a,b]=await Promise.all([fetch(`/api/results/current${demo?'?demo=true':''}`,{cache:'no-store'}),fetch('/api/current',{cache:'no-store'})]);if(!a.ok||!b.ok)throw new Error();render(await a.json(),await b.json())}catch(_){}}applyTheme();load();setInterval(load,1000);
</script></body></html>'''
