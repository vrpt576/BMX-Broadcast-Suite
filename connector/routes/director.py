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
    .results-controls { margin-top:20px; padding-top:16px; border-top:1px solid #2c3947; }
    .results-grid { display:grid; grid-template-columns:1fr 120px; gap:10px; }
    .results-actions { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:10px; }
    .results-status { margin-top:10px; color:#f3b61f; font-weight:800; min-height:1.3em; }
    kbd { display:inline-block; min-width:26px; text-align:center; background:#222d39; border:1px solid #465464; border-bottom-width:3px; border-radius:5px; padding:2px 6px; color:#fff; }
    .lineup { margin-top:18px; }
    .rider { display:grid; grid-template-columns:58px 80px 1fr; gap:8px; padding:8px 10px; border-bottom:1px solid #2c3947; }
    .rider:first-child { border-top:1px solid #2c3947; }
    .gate,.plate { color:#f3b61f; font-weight:900; }
    #message { min-height:1.4em; color:#f3b61f; margin-top:12px; }
    .modal-backdrop { position:fixed; inset:0; z-index:1000; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    .modal-backdrop[hidden] { display:none; }
    .modal { width:min(460px, 94vw); background:#151d27; border:1px solid #52606d; border-radius:14px; padding:20px; box-shadow:0 18px 50px rgba(0,0,0,.6); }
    .modal h2 { margin:0 0 10px; }
    .modal p { color:#c5ced7; line-height:1.45; }
    .modal-check { display:flex; grid-template-columns:22px 1fr; align-items:center; gap:9px; }
    .modal-check input { width:18px; height:18px; }
    .modal-actions { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:18px; }
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
      <details>
        <summary>Remote control access</summary>
        <label>Control token for this browser session<input id="remote-control-token" type="password" autocomplete="off"></label>
        <button id="use-remote-control-token" class="secondary" style="margin-top:10px">Use control token</button>
      </details>
      <div id="moto-number" class="moto-number">1</div>
      <div class="two">
        <button id="previous">◀ Previous Moto</button>
        <button id="next">Next Moto ▶</button>
      </div>
      <div class="two" style="margin-top:10px">
        <button id="previous-round">◀ Previous Round</button>
        <button id="next-round">Next Round ▶</button>
      </div>
      <div class="two" style="margin-top:10px">
        <button id="first-moto" class="secondary">First Moto in Round</button>
        <button id="last-moto" class="secondary">Last Moto in Round</button>
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
      <button id="reset-navigation-confirmation" class="secondary" style="margin-top:10px">Reset navigation confirmation preference</button>
    </section>
    <section class="panel">
      <h2>On-Air Graphic</h2>
      <div class="graphic-buttons">
        <button data-graphic="lineup">L · Show Rider Lineup</button>
        <button data-graphic="current_moto">M · Show Current Moto</button>
        <button id="show-current-results">R · Show Results for Current Moto</button>
        <button data-break="round_1">Show Round 1 Break</button>
        <button data-break="main">Show Main Break</button>
        <button class="danger" data-graphic="hidden">H · Hide All Graphics</button>
      </div>
      <div class="keys">
        <div><kbd>Space</kbd> Next moto</div><div><kbd>Backspace</kbd> Previous moto</div>
        <div><kbd>L</kbd> Lineup</div><div><kbd>M</kbd> Current moto</div>
        <div><kbd>R</kbd> Results</div><div><kbd>H</kbd> Hide graphics</div><div><kbd>[</kbd> <kbd>]</kbd> Change round</div>
      </div>
      <div class="results-controls">
        <h2>Results Roll</h2>
        <div class="results-grid">
          <label>Start from
            <select id="results-start"><option value="first">First available result</option><option value="current">Currently selected moto</option></select>
          </label>
          <label>Seconds
            <input id="results-interval" type="number" min="2" max="300" value="10">
          </label>
        </div>
        <button id="results-start-button" style="margin-top:10px">Start Results Roll</button>
        <div class="results-actions">
          <button id="results-pause" class="secondary">Pause</button>
          <button id="results-resume" class="secondary">Resume</button>
          <button id="results-stop" class="danger">Stop</button>
          <button id="results-previous" class="secondary">Previous Result</button>
          <button id="results-next" class="secondary">Next Result</button>
        </div>
        <div id="results-status" class="results-status">Results Roll stopped.</div>
      </div>
      <div class="lineup">
        <h2>Selected Moto Preview</h2>
        <div id="riders">Waiting for lineup data…</div>
      </div>
      <div id="message" role="status"></div>
    </section>
  </div>
</main>
<div id="navigation-confirm-modal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="navigation-confirm-title" hidden>
  <section class="modal">
    <h2 id="navigation-confirm-title">Confirm race navigation</h2>
    <p id="navigation-confirm-message"></p>
    <label class="modal-check"><input id="navigation-confirm-suppress" type="checkbox"><span>Do not ask again for this event</span></label>
    <div class="modal-actions">
      <button id="navigation-confirm-cancel" class="secondary">Cancel</button>
      <button id="navigation-confirm-accept">Continue</button>
    </div>
  </section>
</div>
<script>
const params=new URLSearchParams(location.search);
const demo=['1','true','yes'].includes((params.get('demo')||'').toLowerCase());
const lineupEndpoint=`/api/lineup/current${demo?'?demo=true':''}`;
const phaseLabels={round_1:'Round 1',round_2:'Round 2',round_3:'Round 3',quarterfinal:'Quarterfinals',semifinal:'Semifinals',main:'Main',overall:'Overall'};
const graphicLabels={hidden:'Hidden',current_moto:'Current Moto',lineup:'Rider Lineup',results:'Results',round_1_break:'Round 1 Break',main_break:'Main Break'};
let state=null;
let events=[];
let program=null;
let mutationVersion=0;
let pendingNavigation=null;
let controlToken='';
const navigationPreferencePrefix='bbs.navigation.confirm.suppressed.';
const $=selector=>document.querySelector(selector);

try{controlToken=sessionStorage.getItem('bbs.control.token')||''}catch(_){}

function authorizedOptions(options={}){
  if(!controlToken)return options;
  const headers=new Headers(options.headers||{});
  headers.set('X-BBS-Control-Token',controlToken);
  return {...options,headers};
}

function navigationEventId(){
  return state?.motoboard_id||state?.resolved_motoboard_id||null;
}

function navigationPreferenceKey(eventId=navigationEventId()){
  return eventId?`${navigationPreferencePrefix}${eventId}`:null;
}

function navigationConfirmationSuppressed(){
  const key=navigationPreferenceKey();
  if(!key)return false;
  try{return localStorage.getItem(key)==='true'}catch(_){return false}
}

function updateNavigationPreferenceControl(){
  const button=$('#reset-navigation-confirmation');
  const eventId=navigationEventId();
  button.disabled=!eventId||!navigationConfirmationSuppressed();
  button.title=eventId?'Reset the remembered choice for this event.':'Select an event before saving a preference.';
}

function closeNavigationConfirmation(){
  $('#navigation-confirm-modal').hidden=true;
  $('#navigation-confirm-suppress').checked=false;
}

function confirmRaceNavigation(message,action){
  if(navigationConfirmationSuppressed())return action();
  pendingNavigation={action,preferenceKey:navigationPreferenceKey()};
  $('#navigation-confirm-message').textContent=message;
  $('#navigation-confirm-suppress').checked=false;
  $('#navigation-confirm-modal').hidden=false;
  $('#navigation-confirm-accept').focus();
}

async function fetchWithTimeout(url,options={},timeoutMs=10000){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{return await fetch(url,{...authorizedOptions(options),signal:controller.signal})}
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
  document.querySelectorAll('[data-break]').forEach(button=>button.classList.toggle('active',`${button.dataset.break}_break`===value.active_graphic));
  $('#show-current-results').classList.toggle('active',value.active_graphic==='results');
  if(value.navigation_message)$('#message').textContent=value.navigation_message;
  updateNavigationPreferenceControl();
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


async function loadProgram(expectedVersion=mutationVersion){
  try{
    const response=await fetchWithTimeout('/api/current/phases',{cache:'no-store'});
    if(!response.ok)throw new Error();
    const phases=await response.json();
    if(expectedVersion!==mutationVersion)return;
    program={available_phases:phases};
    const select=$('#race-phase');
    select.replaceChildren();
    for(const phase of phases){
      const option=document.createElement('option');
      option.value=phase;
      option.textContent=phaseLabels[phase]||phase;
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
  const requestVersion=++mutationVersion;
  const response=await fetch(path,authorizedOptions(options));
  if(!response.ok){
    const body=await response.json().catch(()=>({}));
    throw new Error(body.detail||`Request failed: ${response.status}`);
  }
  const value=await response.json();
  if(requestVersion!==mutationVersion)return value;
  render(value);
  if(!value.navigation_message)$('#message').textContent='';
  await loadProgram(requestVersion);
  await refreshLineup(requestVersion);
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

async function performStep(direction){
  try{await request(`/api/current/${direction}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
}
function step(direction){
  if(direction==='previous'){
    return confirmRaceNavigation('Move backward one moto?',()=>performStep(direction));
  }
  return performStep(direction);
}
async function round(direction){
  try{await request(`/api/current/phase/${direction}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
}
async function graphic(name){
  try{await request(`/api/current/graphic/${name}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
}
async function breakGraphic(preset){
  try{await request(`/api/breaks/show/${preset}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
}
function renderResultsStatus(value){
  const position=value.current_result_index===null?'—':value.current_result_index+1;
  const progress=value.total_available_results?`Moto ${position} of ${value.total_available_results}${value.current_result_moto?` · RaceManager Moto ${value.current_result_moto}`:''}`:'No result loaded';
  const mode=value.active?(value.paused?'Paused':'Running'):'Stopped';
  $('#results-status').textContent=`${mode} · ${progress}`;
  $('#results-pause').disabled=!value.active||value.paused;
  $('#results-resume').disabled=!value.active||!value.paused;
}
async function resultsAction(path,body=null){
  const requestVersion=++mutationVersion;
  try{
    const options={method:'POST'};
    if(body){options.headers={'Content-Type':'application/json'};options.body=JSON.stringify(body)}
    const response=await fetch(`/api/results/${path}`,authorizedOptions(options));
    if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||`Request failed: ${response.status}`)}
    renderResultsStatus(await response.json());
    const currentResponse=await fetch('/api/current',{cache:'no-store'});
    if(currentResponse.ok){
      const value=await currentResponse.json();
      if(requestVersion===mutationVersion)render(value);
    }
  }catch(error){$('#message').textContent=error.message}
}
async function loadResultsStatus(){
  try{const response=await fetch('/api/results/status',{cache:'no-store'});if(response.ok)renderResultsStatus(await response.json())}catch(_){}
}
async function apply(){
  const rawMoto=$('#jump').value.trim();
  if(!/^\d+$/.test(rawMoto)||Number(rawMoto)<1){
    $('#message').textContent='Enter a positive whole-number moto.';
    return;
  }
  const body={
    moto_number:Number(rawMoto),
    race_phase:$('#race-phase').value,
    minimum_moto:1,
    maximum_moto:$('#maximum').value===''?null:Number($('#maximum').value),
    motoboard_id:state?state.motoboard_id:null
  };
  const submit=async()=>{
    try{await request('/api/current',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
    catch(error){$('#message').textContent=error.message}
  };
  if(state&&Number(rawMoto)<state.moto_number){
    return confirmRaceNavigation('Jump backward to an earlier moto?',submit);
  }
  return submit();
}
async function refreshLineup(requestVersion=mutationVersion){
  try{
    const response=await fetchWithTimeout(lineupEndpoint,{cache:'no-store'});
    if(!response.ok)throw new Error();
    const lineup=await response.json();
    if(requestVersion!==mutationVersion)return;
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
$('#first-moto').addEventListener('click',()=>request('/api/current/phase/first',{method:'POST'}).catch(error=>$('#message').textContent=error.message));
$('#last-moto').addEventListener('click',()=>request('/api/current/phase/last',{method:'POST'}).catch(error=>$('#message').textContent=error.message));
$('#apply').addEventListener('click',apply);
$('#navigation-confirm-cancel').addEventListener('click',()=>{
  pendingNavigation=null;
  closeNavigationConfirmation();
});
$('#navigation-confirm-accept').addEventListener('click',()=>{
  const pending=pendingNavigation;
  pendingNavigation=null;
  if(pending&&$('#navigation-confirm-suppress').checked&&pending.preferenceKey){
    try{localStorage.setItem(pending.preferenceKey,'true')}catch(_){}
  }
  closeNavigationConfirmation();
  updateNavigationPreferenceControl();
  if(pending)pending.action();
});
$('#reset-navigation-confirmation').addEventListener('click',()=>{
  const key=navigationPreferenceKey();
  if(key){try{localStorage.removeItem(key)}catch(_){}}
  updateNavigationPreferenceControl();
  $('#message').textContent='Navigation confirmations restored for this event.';
});
$('#remote-control-token').value=controlToken;
$('#use-remote-control-token').addEventListener('click',()=>{
  controlToken=$('#remote-control-token').value.trim();
  try{
    if(controlToken)sessionStorage.setItem('bbs.control.token',controlToken);
    else sessionStorage.removeItem('bbs.control.token');
  }catch(_){}
  $('#message').textContent=controlToken?'Remote control token set for this browser session.':'Remote control token cleared.';
});
$('#event-select').addEventListener('change',selectEvent);
$('#race-phase').addEventListener('change',async()=>{
  try{await request(`/api/current/phase/select/${$('#race-phase').value}`,{method:'POST'})}
  catch(error){$('#message').textContent=error.message}
});
$('#refresh-events').addEventListener('click',loadEvents);
$('#show-current-results').addEventListener('click',()=>resultsAction('show-current'));
$('#results-start-button').addEventListener('click',()=>resultsAction('start',{start_from:$('#results-start').value,interval_seconds:Number($('#results-interval').value)}));
$('#results-pause').addEventListener('click',()=>resultsAction('pause'));
$('#results-resume').addEventListener('click',()=>resultsAction('resume'));
$('#results-previous').addEventListener('click',()=>resultsAction('previous'));
$('#results-next').addEventListener('click',()=>resultsAction('next'));
$('#results-stop').addEventListener('click',()=>resultsAction('stop'));
document.querySelectorAll('[data-graphic]').forEach(button=>button.addEventListener('click',()=>graphic(button.dataset.graphic)));
document.querySelectorAll('[data-break]').forEach(button=>button.addEventListener('click',()=>breakGraphic(button.dataset.break)));
window.addEventListener('keydown',event=>{
  if(['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName))return;
  if(event.key===' '||event.key==='ArrowRight'){event.preventDefault();step('next')}
  else if(event.key==='Backspace'||event.key==='ArrowLeft'){event.preventDefault();step('previous')}
  else if(event.key.toLowerCase()==='l')graphic('lineup');
  else if(event.key.toLowerCase()==='m')graphic('current_moto');
  else if(event.key.toLowerCase()==='r')resultsAction('show-current');
  else if(event.key.toLowerCase()==='h')graphic('hidden');
  else if(event.key===']')round('next');
  else if(event.key==='[')round('previous');
});
request('/api/current').catch(error=>$('#message').textContent=error.message);
loadEvents();
loadResultsStatus();
setInterval(()=>{
  const requestVersion=mutationVersion;
  fetch('/api/current',{cache:'no-store'})
    .then(response=>response.json())
    .then(value=>{if(requestVersion===mutationVersion)render(value)})
    .catch(()=>{});
},1000);
setInterval(loadProgram,5000);
setInterval(loadResultsStatus,1000);
</script>
</body></html>'''
