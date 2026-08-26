"""One consolidated Sqorz status page -- everything needed at the track.

Before this, diagnosing a Sqorz problem on site meant checking /diagnostics,
/sqorz-match-report, and an overlay separately. This page is meant to be
left open on a second monitor: mode, reachability, last successful fetch
and payload age, parsed class/competitor counts, the match report summary,
ambiguous plates, the gate-agreement rate, and (LAN mode) a link to the raw
last response -- so a shape the parser couldn't recognise can be inspected
without a terminal. See connector/services/sqorz_service.py and
docs/sqorz-live-timing.md for what "raw response" does and doesn't prove.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse

from connector.dependencies import get_sqorz_class_alias_store, get_sqorz_service
from connector.services.sqorz_class_alias_service import SqorzClassAliasStore
from connector.services.sqorz_matching import group_by_competitor
from connector.services.sqorz_service import SqorzService

router = APIRouter(tags=["sqorz"])


@router.get("/sqorz/status")
def sqorz_status(
    sqorz: SqorzService = Depends(get_sqorz_service),
    aliases: SqorzClassAliasStore = Depends(get_sqorz_class_alias_store),
) -> dict[str, Any]:
    if not sqorz.enabled:
        return {"enabled": False}

    fetch = sqorz.get_riders()
    report = sqorz.last_match_report
    gate_checks = report.gate_checks if report is not None else {}
    gate_total = (gate_checks.get("agree", 0) + gate_checks.get("disagree", 0)) if gate_checks else 0
    sqorz_classes = sorted({row.class_name for row in fetch.riders if row.class_name})

    return {
        "enabled": True,
        "mode": sqorz.mode,
        "reachable": fetch.reachable,
        "stale": fetch.stale,
        "last_fetch_age_seconds": (
            round(fetch.age_seconds, 1) if fetch.age_seconds is not None else None
        ),
        "last_error": fetch.error,
        "lan_parse_warning": sqorz.last_lan_parse_warning,
        "has_raw_lan_response": sqorz.last_raw_lan_response is not None,
        "class_count": len(sqorz_classes),
        "competitor_count": len(group_by_competitor(fetch.riders)),
        "current_class_name": sqorz.last_match_class_name,
        "current_class_alias": sqorz.last_match_class_alias,
        "sqorz_classes": sqorz_classes,
        "aliases": aliases.all_aliases(),
        "match_report": (
            {
                "counts": report.counts,
                "unmatched_bbs": report.unmatched_bbs,
                "unmatched_sqorz": report.unmatched_sqorz,
                "ambiguous_plates": report.ambiguous_plates,
                "class_match_path": report.class_match_path,
                "gate_checks": gate_checks,
                "gate_agreement_rate": (
                    round(100 * gate_checks.get("agree", 0) / gate_total) if gate_total else None
                ),
            }
            if report is not None
            else None
        ),
    }


@router.get("/sqorz/lan-raw")
def sqorz_lan_raw(sqorz: SqorzService = Depends(get_sqorz_service)) -> JSONResponse:
    """The last raw LAN response(s), for the status page's "view raw
    response" link -- LAN mode only. Kept in memory regardless of whether
    parsing found anything; see SqorzService.last_raw_lan_response."""
    if sqorz.last_raw_lan_response is None:
        return JSONResponse({"available": False})
    return JSONResponse({"available": True, "responses": sqorz.last_raw_lan_response})


async def sqorz_status_page() -> HTMLResponse:
    return HTMLResponse(SQORZ_STATUS_HTML)


SQORZ_STATUS_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BBS Sqorz Status</title>
<style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#f7f7f7;background:#0e141b}*{box-sizing:border-box}body{margin:0;padding:28px}.wrap{max-width:960px;margin:auto}
.muted{color:#aeb9c5}.badge{padding:6px 12px;border-radius:999px;font-weight:800;text-transform:uppercase;font-size:13px;margin-right:6px}.ok{background:#143f2b;color:#83efb8}.attention{background:#552a1f;color:#ffc5aa}.neutral{background:#273444;color:#cfd8e3}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}.card{background:#151e28;border:1px solid #273444;border-radius:12px;padding:14px}
.label{font-size:12px;color:#97a7b8;text-transform:uppercase}.value{font-weight:800;margin-top:6px;font-size:22px}
.section{margin:22px 0}h2{font-size:15px;text-transform:uppercase;color:#97a7b8;letter-spacing:.05em;margin-bottom:8px}
.names{background:#151e28;border:1px solid #273444;border-radius:10px;padding:12px;max-height:220px;overflow:auto;font-size:14px;line-height:1.7}
.ambiguous{background:#2a1a12;border:1px solid #6b3a1f;border-radius:10px;padding:12px;color:#ffc5aa;font-size:14px;line-height:1.7}
.warning-box{background:#2a1a12;border:1px solid #6b3a1f;border-radius:10px;padding:12px;color:#ffc5aa;font-size:14px;line-height:1.6}
.form{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin-top:10px}
label{display:block;font-size:12px;color:#97a7b8;margin-bottom:5px}
select,input{padding:9px;border-radius:8px;border:1px solid #415064;background:#0d131a;color:#fff;min-width:220px}
button{padding:10px 16px;border:0;border-radius:9px;background:#f5b821;font-weight:900;cursor:pointer}
#status{margin-left:8px}
pre{white-space:pre-wrap;word-break:break-word;background:#0d131a;border:1px solid #273444;border-radius:10px;padding:12px;max-height:400px;overflow:auto;font-size:12px}
.disclaimer{color:#ffc5aa;font-weight:700}
</style></head><body><main class="wrap">
<h1>Sqorz Status</h1>
<p class="muted">Leave this open. Refreshes automatically every 3 seconds.</p>
<div id="summary"></div>
<div class="grid" id="counts"></div>
<div class="section" id="lan-warning-section" style="display:none"><h2>LAN parsing</h2><div class="warning-box" id="lan-warning"></div></div>
<div class="section"><h2>Unmatched (BBS side -- no Sqorz counterpart found)</h2><div class="names" id="unmatched-bbs"></div></div>
<div class="section"><h2>Unmatched (Sqorz side -- no BBS counterpart found)</h2><div class="names" id="unmatched-sqorz"></div></div>
<div class="section" id="ambiguous-section" style="display:none"><h2>Ambiguous plates</h2><div class="ambiguous" id="ambiguous"></div></div>
<div class="section"><h2>Set a class alias</h2>
<p class="muted">Point the current BBS class at the right Sqorz class. Takes effect on the next poll, no restart.</p>
<div class="form">
  <div><label>Sqorz class</label><select id="sqorz-class"></select></div>
  <button id="save">Save alias for current class</button>
  <button id="clear">Clear alias</button>
  <span id="status" class="muted"></span>
</div>
</div>
<div class="section" id="raw-section" style="display:none">
  <h2>Raw LAN response</h2>
  <p class="muted disclaimer">This shows what Sqorz actually sent back -- it is resilience, not verification. A response appearing here does not confirm the parser reads it correctly, only that something was received.</p>
  <button id="load-raw">View raw response</button>
  <pre id="raw-content" style="display:none"></pre>
</div>
</main>
<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(){
  const r=await fetch('/api/sqorz/status',{cache:'no-store'});
  const d=await r.json();
  const summary=document.querySelector('#summary');
  if(!d.enabled){summary.innerHTML='<span class="badge attention">DISABLED</span>';document.querySelector('#counts').innerHTML='';document.querySelector('#raw-section').style.display='none';return}
  const badges=[
    '<span class="badge neutral">'+esc((d.mode||'').toUpperCase())+' MODE</span>',
    '<span class="badge '+(d.reachable?'ok':'attention')+'">'+(d.reachable?'REACHABLE':'UNREACHABLE')+'</span>',
  ];
  if(d.stale) badges.push('<span class="badge attention">STALE</span>');
  summary.innerHTML=badges.join(' ')+' <span class="muted">'
    +(d.last_error?esc(d.last_error):'Current class: <strong>'+esc(d.current_class_name||'(none yet -- open the lineup or Director once)')+'</strong>'+(d.current_class_alias?' &nbsp;alias &rarr; '+esc(d.current_class_alias):''))
    +'</span>';

  const counts=(d.match_report&&d.match_report.counts)||{};
  const gateTotal=((d.match_report&&d.match_report.gate_checks&&d.match_report.gate_checks.agree)||0)+((d.match_report&&d.match_report.gate_checks&&d.match_report.gate_checks.disagree)||0);
  const gateRate=gateTotal?(d.match_report.gate_agreement_rate+'% ('+d.match_report.gate_checks.agree+'/'+gateTotal+')'):'—';
  document.querySelector('#counts').innerHTML=
    '<div class="card"><div class="label">Payload age</div><div class="value" style="font-size:16px">'+(d.last_fetch_age_seconds==null?'—':d.last_fetch_age_seconds+'s')+'</div></div>'
    +'<div class="card"><div class="label">Classes parsed</div><div class="value">'+esc(d.class_count)+'</div></div>'
    +'<div class="card"><div class="label">Competitors parsed</div><div class="value">'+esc(d.competitor_count)+'</div></div>'
    +['exact','strong','weak','none'].map(k=>'<div class="card"><div class="label">'+k+'</div><div class="value">'+esc(counts[k]??0)+'</div></div>').join('')
    +'<div class="card"><div class="label">Match path</div><div class="value" style="font-size:16px">'+esc((d.match_report&&d.match_report.class_match_path)||'—')+'</div></div>'
    +'<div class="card"><div class="label">Gate agreement</div><div class="value" style="font-size:16px">'+esc(gateRate)+'</div></div>';

  const warnSection=document.querySelector('#lan-warning-section');
  if(d.lan_parse_warning){warnSection.style.display='block';document.querySelector('#lan-warning').textContent=d.lan_parse_warning}
  else{warnSection.style.display='none'}

  document.querySelector('#unmatched-bbs').innerHTML=(d.match_report&&d.match_report.unmatched_bbs.length?d.match_report.unmatched_bbs.map(esc).join('<br>'):'<span class="muted">none</span>');
  document.querySelector('#unmatched-sqorz').innerHTML=(d.match_report&&d.match_report.unmatched_sqorz.length?d.match_report.unmatched_sqorz.map(esc).join('<br>'):'<span class="muted">none</span>');
  const ambiguous=(d.match_report&&d.match_report.ambiguous_plates)||[];
  document.querySelector('#ambiguous-section').style.display=ambiguous.length?'block':'none';
  document.querySelector('#ambiguous').innerHTML=ambiguous.map(esc).join('<br>');

  const select=document.querySelector('#sqorz-class');
  const current=select.value;
  select.innerHTML='<option value="">— select —</option>'+d.sqorz_classes.map(c=>'<option value="'+esc(c)+'">'+esc(c)+'</option>').join('');
  if(current)select.value=current;
  window.__currentClass=d.current_class_name;

  document.querySelector('#raw-section').style.display=(d.mode==='lan')?'block':'none';
}
async function save(clear){
  const status=document.querySelector('#status');
  const bbsClass=window.__currentClass;
  if(!bbsClass){status.textContent='No current class yet -- open the lineup or Director first.';return}
  const sqorzClass=clear?null:document.querySelector('#sqorz-class').value;
  const r=await fetch('/api/sqorz/aliases',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({bbs_class_name:bbsClass,sqorz_class_name:sqorzClass})});
  const d=await r.json();
  status.textContent=d.saved?'Saved.':(d.message||'Failed.');
  load();
}
async function loadRaw(){
  const pre=document.querySelector('#raw-content');
  const r=await fetch('/api/sqorz/lan-raw',{cache:'no-store'});
  const d=await r.json();
  pre.textContent=d.available?JSON.stringify(d.responses,null,2):'No raw response captured yet -- Sqorz has not been polled in LAN mode yet.';
  pre.style.display='block';
}
document.querySelector('#save').addEventListener('click',()=>save(false));
document.querySelector('#clear').addEventListener('click',()=>save(true));
document.querySelector('#load-raw').addEventListener('click',loadRaw);
load();
setInterval(load,3000);
</script>
</body></html>'''
