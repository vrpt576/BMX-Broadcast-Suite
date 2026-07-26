"""Race Director control surface for live broadcast operation."""

from fastapi.responses import HTMLResponse


def race_director_page() -> str:
    return DIRECTOR_HTML


DIRECTOR_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BBS Race Director</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin:0; min-height:100vh; background:#0b1016; color:#fff; }
    main { width:min(1180px, 94vw); margin:0 auto; padding:28px 0 48px; }
    h1 { margin:0; font-size:2rem; }
    .sub { color:#aeb8c4; margin:.35rem 0 1.5rem; }
    .statusbar { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:18px; }
    .stat { background:#151d27; border:1px solid #2c3947; border-radius:12px; padding:14px; }
    .stat small { display:block; color:#9eabb8; text-transform:uppercase; letter-spacing:.08em; }
    .stat strong { display:block; margin-top:4px; font-size:1.35rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .grid { display:grid; grid-template-columns:1.1fr .9fr; gap:18px; }
    .panel { background:#111820; border:1px solid #2c3947; border-radius:14px; padding:18px; }
    .panel h2 { margin:0 0 14px; font-size:1.15rem; }
    .moto-number { font-size:8rem; line-height:.9; font-weight:950; text-align:center; margin:18px 0; }
    .two { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .three { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
    button, input, select { width:100%; font:inherit; border-radius:9px; border:1px solid #52606d; padding:12px; }
    button { cursor:pointer; background:#e5e7eb; color:#101820; font-weight:850; }
    button:hover { filter:brightness(1.08); }
    button.active { background:#f3b61f; color:#101820; border-color:#f3b61f; }
    button.danger { background:#7d2431; color:#fff; border-color:#a63c4b; }
    label { display:grid; gap:6px; color:#c5ced7; font-size:.9rem; margin-top:12px; }
    .graphic-buttons { display:grid; gap:10px; }
    .graphic-buttons button { min-height:68px; font-size:1.15rem; }
    .keys { margin-top:16px; display:grid; grid-template-columns:repeat(2,1fr); gap:6px 16px; color:#aeb8c4; font-size:.9rem; }
    kbd { display:inline-block; min-width:26px; text-align:center; background:#222d39; border:1px solid #465464; border-bottom-width:3px; border-radius:5px; padding:2px 6px; color:#fff; }
    .lineup { margin-top:18px; }
    .rider { display:grid; grid-template-columns:58px 80px 1fr; gap:8px; padding:8px 10px; border-bottom:1px solid #2c3947; }
    .rider:first-child { border-top:1px solid #2c3947; }
    .gate,.plate { color:#f3b61f; font-weight:900; }
    #message { min-height:1.4em; color:#f3b61f; margin-top:12px; }
    @media(max-width:800px){ .grid,.statusbar{grid-template-columns:1fr 1fr}.moto-number{font-size:6rem} }
    @media(max-width:540px){ .grid,.statusbar{grid-template-columns:1fr}.three{grid-template-columns:1fr} }
  </style>
</head>
<body>
<main>
  <h1>BBS Race Director</h1>
  <p class="sub">One control surface for race position and on-air graphics.</p>
  <section class="statusbar">
    <div class="stat"><small>Round</small><strong id="round-stat">Round 1</strong></div>
    <div class="stat"><small>Class</small><strong id="class-stat">Class not set</strong></div>
    <div class="stat"><small>Moto</small><strong id="moto-stat">1</strong></div>
    <div class="stat"><small>On Air</small><strong id="graphic-stat">Current Moto</strong></div>
  </section>
  <div class="grid">
    <section class="panel">
      <h2>Race Position</h2>
      <div id="moto-number" class="moto-number">1</div>
      <div class="two">
        <button id="previous">◀ Previous Moto</button>
        <button id="next">Next Moto ▶</button>
      </div>
      <div class="two" style="margin-top:10px">
        <button id="previous-round">◀ Previous Round</button>
        <button id="next-round">Next Round ▶</button>
      </div>
      <label>Race round
        <select id="race-phase">
          <option value="round_1">Round 1</option><option value="round_2">Round 2</option>
          <option value="round_3">Round 3</option><option value="quarterfinal">Quarterfinals</option>
          <option value="semifinal">Semifinals</option><option value="main">Mains</option>
        </select>
      </label>
      <label>Class name<input id="class-name" maxlength="100" placeholder="17-20 Expert"></label>
      <div class="two">
        <label>Jump to moto<input id="jump" type="number" min="1"></label>
        <label>Last moto (optional)<input id="maximum" type="number" min="1"></label>
      </div>
      <button id="apply" style="margin-top:12px">Apply Race Position</button>
    </section>
    <section class="panel">
      <h2>On-Air Graphic</h2>
      <div class="graphic-buttons">
        <button data-graphic="lineup">L · Show Rider Lineup</button>
        <button data-graphic="current_moto">M · Show Current Moto</button>
        <button class="danger" data-graphic="hidden">H · Hide All Graphics</button>
      </div>
      <div class="keys">
        <div><kbd>Space</kbd> Next moto</div><div><kbd>Backspace</kbd> Previous moto</div>
        <div><kbd>L</kbd> Lineup</div><div><kbd>M</kbd> Current moto</div>
        <div><kbd>H</kbd> Hide graphics</div><div><kbd>[</kbd> <kbd>]</kbd> Change round</div>
      </div>
      <div class="lineup">
        <h2>Selected Moto Preview</h2>
        <div id="riders">Waiting for lineup data…</div>
      </div>
      <div id="message" role="status"></div>
    </section>
  </div>
</main>
<script>
const params=new URLSearchParams(location.search);
const demo=['1','true','yes'].includes((params.get('demo')||'').toLowerCase());
const lineupEndpoint=`/api/lineup/current${demo?'?demo=true':''}`;
const phaseLabels={round_1:'Round 1',round_2:'Round 2',round_3:'Round 3',quarterfinal:'Quarterfinals',semifinal:'Semifinals',main:'Mains'};
const graphicLabels={hidden:'Hidden',current_moto:'Current Moto',lineup:'Rider Lineup'};
let state=null;
const $=s=>document.querySelector(s);
function render(value){
 state=value; $('#round-stat').textContent=phaseLabels[value.race_phase]||value.race_phase;
 $('#class-stat').textContent=value.class_name||'Class not set'; $('#moto-stat').textContent=value.moto_number;
 $('#moto-number').textContent=value.moto_number; $('#graphic-stat').textContent=graphicLabels[value.active_graphic]||value.active_graphic;
 $('#race-phase').value=value.race_phase; $('#class-name').value=value.class_name||''; $('#jump').value=value.moto_number; $('#maximum').value=value.maximum_moto??'';
 document.querySelectorAll('[data-graphic]').forEach(b=>b.classList.toggle('active',b.dataset.graphic===value.active_graphic));
}
async function request(path,options={}){ const r=await fetch(path,options); if(!r.ok){const b=await r.json().catch(()=>({}));throw new Error(b.detail||`Request failed: ${r.status}`)} const v=await r.json(); render(v); await refreshLineup(); return v; }
async function step(dir){try{await request(`/api/current/${dir}`,{method:'POST'})}catch(e){$('#message').textContent=e.message}}
async function round(dir){try{await request(`/api/current/phase/${dir}`,{method:'POST'})}catch(e){$('#message').textContent=e.message}}
async function graphic(name){try{await request(`/api/current/graphic/${name}`,{method:'POST'})}catch(e){$('#message').textContent=e.message}}
async function apply(){const body={moto_number:Number($('#jump').value),race_phase:$('#race-phase').value,class_name:$('#class-name').value,minimum_moto:1};if($('#maximum').value!=='')body.maximum_moto=Number($('#maximum').value);try{await request('/api/current',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}catch(e){$('#message').textContent=e.message}}
async function refreshLineup(){try{const r=await fetch(lineupEndpoint,{cache:'no-store'});if(!r.ok)throw new Error();const l=await r.json();if(l.source==='database'&&l.class_name)$('#class-stat').textContent=l.class_name;const box=$('#riders');box.replaceChildren();for(const rider of l.riders){const row=document.createElement('div');row.className='rider';row.innerHTML=`<span class="gate">${rider.gate??'—'}</span><span class="plate">${rider.bike_number??'—'}</span><span></span>`;row.lastElementChild.textContent=`${rider.first_name} ${rider.last_name}`;box.append(row)}if(!l.riders.length)box.textContent='No riders assigned.'}catch(_){$('#riders').textContent='RaceManager lineup unavailable.'}}
$('#previous').addEventListener('click',()=>step('previous'));$('#next').addEventListener('click',()=>step('next'));$('#previous-round').addEventListener('click',()=>round('previous'));$('#next-round').addEventListener('click',()=>round('next'));$('#apply').addEventListener('click',apply);document.querySelectorAll('[data-graphic]').forEach(b=>b.addEventListener('click',()=>graphic(b.dataset.graphic)));
window.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName))return;if(e.key===' '||e.key==='ArrowRight'){e.preventDefault();step('next')}else if(e.key==='Backspace'||e.key==='ArrowLeft'){e.preventDefault();step('previous')}else if(e.key.toLowerCase()==='l')graphic('lineup');else if(e.key.toLowerCase()==='m')graphic('current_moto');else if(e.key.toLowerCase()==='h')graphic('hidden');else if(e.key===']')round('next');else if(e.key==='[')round('previous')});
request('/api/current').catch(e=>$('#message').textContent=e.message);setInterval(()=>fetch('/api/current',{cache:'no-store'}).then(r=>r.json()).then(render).catch(()=>{}),1000);
</script>
</body></html>'''
