"""Experimental current-results API and OBS overlay."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from connector.dependencies import get_current_results_service
from connector.models import CurrentResults
from connector.services.current_results_service import CurrentResultsService

router=APIRouter(tags=['results'])

@router.get('/results/current',response_model=CurrentResults)
def current_results(demo:bool=Query(False),service:CurrentResultsService=Depends(get_current_results_service))->CurrentResults:
    return service.get(demo=demo)

def results_overlay()->str:return RESULTS_HTML

RESULTS_HTML=r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>BBS Results</title><style>
:root{--primary:#f3b61f;--panel:#101820;--text:#fff;font-family:Arial,sans-serif}*{box-sizing:border-box}body{margin:0;width:100vw;height:100vh;background:transparent;overflow:hidden}.wrap{position:absolute;left:4vw;bottom:5vh;width:min(760px,92vw);filter:drop-shadow(0 6px 12px #0008)}.head{display:flex;width:max-content;max-width:100%}.head div{padding:.35em .7em;font-size:27px;font-weight:900;text-transform:uppercase}.phase,.moto{background:var(--primary);color:#101820}.class{background:var(--panel);color:var(--text)}.rows{border-top:4px solid var(--primary);background:var(--panel);color:var(--text)}.row{display:grid;grid-template-columns:75px 130px 1fr;min-height:58px;align-items:center;border-bottom:1px solid #ffffff2b;font-size:27px;font-weight:800}.place{height:100%;display:grid;place-items:center;background:var(--primary);color:#101820}.plate{color:var(--primary);text-align:center}.name{text-transform:uppercase}.stale{background:#7f1d1d;color:white;padding:.35em .7em;font-weight:800;display:none}
</style></head><body><section class="wrap"><div id="stale" class="stale">LAST KNOWN DATA</div><div id="graphic"><div class="head"><div id="phase" class="phase">ROUND 1</div><div id="class" class="class">CLASS</div><div id="moto" class="moto">MOTO 1</div></div><div id="rows" class="rows"></div></div></section><script>
const p=new URLSearchParams(location.search),demo=['1','true','yes'].includes((p.get('demo')||'').toLowerCase()),preview=['1','true','yes'].includes((p.get('preview')||'').toLowerCase());const labels={round_1:'ROUND 1',round_2:'ROUND 2',round_3:'ROUND 3',quarterfinal:'QUARTERFINALS',semifinal:'SEMIFINALS',main:'MAINS'};
function render(s,c){document.body.style.visibility=(preview||c.active_graphic==='results')?'visible':'hidden';phase.textContent=labels[s.race_phase]||s.race_phase;document.querySelector('#class').textContent=s.class_name;moto.textContent=`MOTO ${s.moto_number}`;stale.style.display=s.is_stale?'block':'none';rows.replaceChildren();for(const r of s.riders){const d=document.createElement('div');d.className='row';d.innerHTML=`<div class="place">${r.finish??'—'}</div><div class="plate">${r.bike_number??'—'}</div><div class="name"></div>`;d.lastElementChild.textContent=`${r.first_name} ${r.last_name}`;rows.append(d)}}
async function load(){try{const [a,b]=await Promise.all([fetch(`/api/results/current${demo?'?demo=true':''}`,{cache:'no-store'}),fetch('/api/current',{cache:'no-store'})]);render(await a.json(),await b.json())}catch(_){}}load();setInterval(load,1000);
</script></body></html>'''
