"""Race Director control surface for live broadcast operation."""


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
    .statusbar { display:grid; grid-template-columns:1.35fr repeat(4,1fr); gap:12px; margin-bottom:18px; }
    .stat { background:#151d27; border:1px solid #2c3947; border-radius:12px; padding:14px; min-width:0; }
    .stat small { display:block; color:#9eabb8; text-transform:uppercase; letter-spacing:.08em; }
    .stat strong { display:block; margin-top:4px; font-size:1.25rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .grid { display:grid; grid-template-columns:1.1fr .9fr; gap:18px; }
    .panel { background:#111820; border:1px solid #2c3947; border-radius:14px; padding:18px; }
    .panel h2 { margin:0 0 14px; font-size:1.15rem; }
    .moto-number { font-size:8rem; line-height:.9; font-weight:950; text-align:center; margin:18px 0; }
    .two { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    button, input, select { width:100%; font:inherit; border-radius:9px; border:1px solid #52606d; padding:12px; }
    button { cursor:pointer; background:#e5e7eb; color:#101820; font-weight:850; }
    button:hover { filter:brightness(1.08); }
    button:disabled { cursor:wait; opacity:.65; }
    button.active { background:#f3b61f; color:#101820; border-color:#f3b61f; }
    button.danger { background:#7d2431; color:#fff; border-color:#a63c4b; }
    button.secondary { background:#222d39; color:#fff; border-color:#465464; }
    label { display:grid; gap:6px; color:#c5ced7; font-size:.9rem; margin-top:12px; }
    .event-picker { display:grid; grid-template-columns:1fr 150px; gap:10px; align-items:end; margin-bottom:8px; }
    .event-picker label { margin-top:0; }
    .event-detail { color:#9eabb8; min-height:1.3em; font-size:.86rem; margin:4px 0 14px; }
    .graphic-buttons { display:grid; gap:10px; }
    .graphic-buttons button { min-height:68px; font-size:1.15rem; }
    .keys { margin-top:16px; display:grid; grid-template-columns:repeat(2,1fr); gap:6px 16px; color:#aeb8c4; font-size:.9rem; }
    kbd { display:inline-block; min-width:26px; text-align:center; background:#222d39; border:1px solid #465464; border-bottom-width:3px; border-radius:5px; padding:2px 6px; color:#fff; }
    .lineup { margin-top:18px; }
    .rider { display:grid; grid-template-columns:58px 80px 1fr; gap:8px; padding:8px 10px; border-bottom:1px solid #2c3947; }
    .rider:first-child { border-top:1px solid #2c3947; }
    .gate,.plate { color:#f3b61f; font-weight:900; }
    #message { min-height:1.4em; color:#f3b61f; margin-top:12px; }
    @media(max-width:900px){ .statusbar{grid-template-columns:repeat(3,1fr)} }
    @media(max-width:800px){ .grid{grid-template-columns:1fr}.moto-number{font-size:6rem} }
    @media(max-width:540px){ .statusbar,.two,.event-picker{grid-template-columns:1fr} }
  </style>
</head>
<body>
<main>
  <h1>BBS Race Director</h1>
  <p class="sub">One control surface for race position, event selection, and on-air graphics.</p>
  <section class="statusbar">
    <div class="stat"><small>Event</small><strong id="event-stat">Latest / Live</strong></div>
    <div class="stat"><small>Round</small><strong id="round-stat">Round 1</strong></div>
    <div class="stat"><small>Class</small><strong id="class-stat">Class not set</strong></div>
    <div class="stat"><small>Moto</small><strong id="moto-stat">1</strong></div>
    <div class="stat"><small>On Air</small><strong id="graphic-stat">Current Moto</strong></div>
  </section>
  <div class="grid">
    <section class="panel">
      <h2>Race Position</h2>
      <div class="event-picker">
        <label>RaceManager event / race
          <select id="event-select"><option value="">Latest / Live (automatic)</option></select>
        </label>
        <button id="refresh-events" class="secondary">Refresh Events</button>
      </div>
      <div id="event-detail" class="event-detail">Uses the newest RaceManager motoboard automatically.</div>
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
        <button data-graphic="results">R · Show Results (Experimental)</button>
        <button class="danger" data-graphic="hidden">H · Hide All Graphics</button>
      </div>
      <div class="keys">
        <div><kbd>Space</kbd> Next moto</div><div><kbd>Backspace</kbd> Previous moto</div>
        <div><kbd>L</kbd> Lineup</div><div><kbd>M</kbd> Current moto</div>
        <div><kbd>R</kbd> Results</div><div><kbd>H</kbd> Hide graphics</div><div><kbd>[</kbd> <kbd>]</kbd> Change round</div>
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
const phaseLabels={round_1:'Round 1',round_2:'Round 2',round_3:'Round 3',quarterfinal:'Quarterfinals',semifinal:'Semifinals',main:'Main',overall:'Overall'};
const graphicLabels={hidden:'Hidden',current_moto:'Current Moto',lineup:'Rider Lineup',results:'Results'};
let state=null;
let events=[];
let program=null;
const $=selector=>document.querySelector(selector);

async function fetchWithTimeout(url,options={},timeoutMs=2800){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{return await fetch(url,{...options,signal:controller.signal})}
  finally{clearTimeout(timer)}
}

function eventOptionLabel(event){
  const date=(event.date_begin||'').toString().slice(0,10)||'Date unknown';
  const race=event.race_description||'Race';
  return `${date} — ${event.event_name} — ${race}`;
}

function renderEventSelection(value){
  const select=$('#event-select');
  const boardId=value.motoboard_id||'';
  const selected=events.find(event=>event.motoboard_id===boardId);
  if(boardId&&!selected&&!Array.from(select.options).some(option=>option.value===boardId)){
    const option=document.createElement('option');
    option.value=boardId;
    option.textContent='Selected historic event (details unavailable)';
    select.append(option);
  }
  select.value=boardId;
  if(!boardId){
    $('#event-stat').textContent='Latest / Live';
    $('#event-detail').textContent='Uses the newest RaceManager motoboard automatically.';
  }else if(selected){
    $('#event-stat').textContent=selected.event_name;
    $('#event-detail').textContent=`${eventOptionLabel(selected)} · ${selected.total_motos} motos · ${selected.total_riders} riders`;
  }else{
    $('#event-stat').textContent='Historic event';
    $('#event-detail').textContent=`Pinned motoboard ${boardId}; RaceManager details are currently unavailable.`;
  }
}

function render(value){
  state=value;
  $('#round-stat').textContent=value.phase_label||phaseLabels[value.race_phase]||value.race_phase;
  $('#class-stat').textContent=value.class_name||'Class not set';
  $('#moto-stat').textContent=value.moto_number;
  $('#moto-number').textContent=value.moto_number;
  $('#graphic-stat').textContent=graphicLabels[value.active_graphic]||value.active_graphic;
  $('#race-phase').value=value.race_phase;
  $('#class-name').value=value.class_name||'';
  $('#jump').value=value.moto_number;
  $('#maximum').value=value.maximum_moto??'';
  renderEventSelection(value);
  document.querySelectorAll('[data-graphic]').forEach(button=>button.classList.toggle('active',button.dataset.graphic===value.active_graphic));
}

async function loadEvents(){
  const button=$('#refresh-events');
  button.disabled=true;
  try{
    const response=await fetchWithTimeout('/api/event',{cache:'no-store'});
    if(!response.ok)throw new Error(`Request failed: ${response.status}`);
    events=await response.json();
    const select=$('#event-select');
    select.replaceChildren();
    const live=document.createElement('option');
    live.value='';
    live.textContent='Latest / Live (automatic)';
    select.append(live);
    for(const event of events){
      const option=document.createElement('option');
      option.value=event.motoboard_id;
      option.textContent=eventOptionLabel(event);
      select.append(option);
    }
    if(state)renderEventSelection(state);
    if(!events.length)$('#message').textContent='No RaceManager events with motoboards were found.';
    else if($('#message').textContent.includes('event list'))$('#message').textContent='';
  }catch(error){
    if(state)renderEventSelection(state);
    $('#message').textContent='RaceManager event list unavailable — manual controls remain available.';
  }finally{
    button.disabled=false;
  }
}


async function loadProgram(){
  try{
    const response=await fetchWithTimeout('/api/current/program',{cache:'no-store'});
    if(!response.ok)throw new Error();
    program=await response.json();
    const select=$('#race-phase');
    select.replaceChildren();
    for(const stage of program.stages){
      const option=document.createElement('option');
      option.value=stage.phase;
      option.textContent=stage.label;
      select.append(option);
    }
    if(state)select.value=state.race_phase;
    $('#previous-round').disabled=program.available_phases.indexOf(state?.race_phase)<=0;
    $('#next-round').disabled=program.available_phases.indexOf(state?.race_phase)>=program.available_phases.length-1;
  }catch(_){
    program=null;
    const select=$('#race-phase');
    if(!select.options.length)select.add(new Option('Round 1','round_1'));
  }
}

async function request(path,options={}){
  const response=await fetch(path,options);
  if(!response.ok){
    const body=await response.json().catch(()=>({}));
    throw new Error(body.detail||`Request failed: ${response.status}`);
  }
  const value=await response.json();
  render(value);
  await loadProgram();
  await refreshLineup();
  return value;
}

async function selectEvent(){
  if(!state)return;
  const boardId=$('#event-select').value||null;
  const moto=Math.max(state.moto_number,1);
  const body={
    moto_number:moto,
    race_phase:'round_1',
    minimum_moto:1,
    maximum_moto:null,
    motoboard_id:boardId,
    active_graphic:state.active_graphic
  };
  try{
    $('#message').textContent=boardId?'Selecting historic event…':'Returning to Latest / Live…';
    await request('/api/current',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    $('#message').textContent=boardId?'Historic event selected.':'Latest / Live selection restored.';
  }catch(error){
    $('#message').textContent=error.message;
    renderEventSelection(state);
  }
}

async function step(direction){
  if(direction==='previous'&&!confirm('Move backward one moto?'))return;
  try{await request(`/api/current/${direction}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
}
async function round(direction){
  try{await request(`/api/current/phase/${direction}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
}
async function graphic(name){
  try{await request(`/api/current/graphic/${name}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
}
async function apply(){
  if(state&&Number($('#jump').value)<state.moto_number&&!confirm('Jump backward to an earlier moto?'))return;
  const body={
    moto_number:Number($('#jump').value),
    race_phase:'round_1',
    minimum_moto:1,
    maximum_moto:$('#maximum').value===''?null:Number($('#maximum').value),
    motoboard_id:state?state.motoboard_id:null
  };
  try{await request('/api/current',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
  catch(error){$('#message').textContent=error.message}
}
async function refreshLineup(){
  try{
    const response=await fetchWithTimeout(lineupEndpoint,{cache:'no-store'});
    if(!response.ok)throw new Error();
    const lineup=await response.json();
    if((lineup.source==='racemanager'||lineup.source==='cache')&&lineup.class_name)$('#class-stat').textContent=lineup.class_name;
    const box=$('#riders');
    box.replaceChildren();
    for(const rider of lineup.riders){
      const row=document.createElement('div');
      row.className='rider';
      row.innerHTML=`<span class="gate">${rider.gate??'—'}</span><span class="plate">${rider.bike_number??'—'}</span><span></span>`;
      row.lastElementChild.textContent=`${rider.first_name} ${rider.last_name}`;
      box.append(row);
    }
    if(!lineup.riders.length)box.textContent='No riders assigned.';
    if(lineup.is_stale)$('#message').textContent='Database offline — showing last known lineup.';
  }catch(_){
    $('#riders').textContent='RaceManager lineup unavailable.';
  }
}

$('#previous').addEventListener('click',()=>step('previous'));
$('#next').addEventListener('click',()=>step('next'));
$('#previous-round').addEventListener('click',()=>round('previous'));
$('#next-round').addEventListener('click',()=>round('next'));
$('#apply').addEventListener('click',apply);
$('#event-select').addEventListener('change',selectEvent);
$('#race-phase').addEventListener('change',async()=>{
  try{await request(`/api/current/phase/select/${$('#race-phase').value}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
});
$('#refresh-events').addEventListener('click',loadEvents);
document.querySelectorAll('[data-graphic]').forEach(button=>button.addEventListener('click',()=>graphic(button.dataset.graphic)));
window.addEventListener('keydown',event=>{
  if(['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName))return;
  if(event.key===' '||event.key==='ArrowRight'){event.preventDefault();step('next')}
  else if(event.key==='Backspace'||event.key==='ArrowLeft'){event.preventDefault();step('previous')}
  else if(event.key.toLowerCase()==='l')graphic('lineup');
  else if(event.key.toLowerCase()==='m')graphic('current_moto');
  else if(event.key.toLowerCase()==='r')graphic('results');
  else if(event.key.toLowerCase()==='h')graphic('hidden');
  else if(event.key===']')round('next');
  else if(event.key==='[')round('previous');
});
request('/api/current').catch(error=>$('#message').textContent=error.message);
loadEvents();
setInterval(()=>fetch('/api/current',{cache:'no-store'}).then(response=>response.json()).then(render).catch(()=>{}),1000);
setInterval(loadProgram,5000);
</script>
</body></html>'''
