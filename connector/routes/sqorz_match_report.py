"""Visible Sqorz match report + operator-editable class aliases.

The tool an operator actually needs at the track when a class isn't lining
up: what matched, what didn't on each side, any ambiguous-plate collisions,
and a way to point BBS at the right Sqorz class without editing a file by
hand (though that file -- see SqorzClassAliasStore -- is documented as the
fallback in docs/sqorz-on-site-runbook.md).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import HTMLResponse

from connector.dependencies import get_sqorz_class_alias_store, get_sqorz_service
from connector.services.sqorz_class_alias_service import SqorzClassAliasStore
from connector.services.sqorz_service import SqorzService

router = APIRouter(tags=["sqorz"])


@router.get("/sqorz/match-report")
def sqorz_match_report(
    sqorz: SqorzService = Depends(get_sqorz_service),
    aliases: SqorzClassAliasStore = Depends(get_sqorz_class_alias_store),
) -> dict[str, Any]:
    fetch = sqorz.get_riders() if sqorz.enabled else None
    sqorz_classes = sorted(
        {row.class_name for row in (fetch.riders if fetch else []) if row.class_name}
    )
    report = sqorz.last_match_report
    class_name = sqorz.last_match_class_name
    return {
        "sqorz_enabled": sqorz.enabled,
        "sqorz_reachable": fetch.reachable if fetch else False,
        "current_class_name": class_name,
        "current_class_alias": sqorz.last_match_class_alias,
        "sqorz_classes": sqorz_classes,
        "aliases": aliases.all_aliases(),
        "report": (
            {
                "counts": report.counts,
                "unmatched_bbs": report.unmatched_bbs,
                "unmatched_sqorz": report.unmatched_sqorz,
                "ambiguous_plates": report.ambiguous_plates,
                "class_match_path": report.class_match_path,
                "gate_checks": report.gate_checks,
            }
            if report is not None
            else None
        ),
    }


@router.put("/sqorz/aliases")
def save_sqorz_alias(
    payload: dict[str, Any] = Body(...),
    aliases: SqorzClassAliasStore = Depends(get_sqorz_class_alias_store),
) -> dict[str, Any]:
    bbs_class_name = str(payload.get("bbs_class_name") or "").strip()
    sqorz_class_name = payload.get("sqorz_class_name")
    if not bbs_class_name:
        return {"saved": False, "message": "bbs_class_name is required.", "aliases": aliases.all_aliases()}
    aliases.set_alias(bbs_class_name, sqorz_class_name)
    return {"saved": True, "aliases": aliases.all_aliases()}


async def sqorz_match_report_page() -> HTMLResponse:
    return HTMLResponse(SQORZ_MATCH_REPORT_HTML)


SQORZ_MATCH_REPORT_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BBS Sqorz Match Report</title>
<style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#f7f7f7;background:#0e141b}*{box-sizing:border-box}body{margin:0;padding:28px}.wrap{max-width:900px;margin:auto}
.muted{color:#aeb9c5}.badge{padding:6px 12px;border-radius:999px;font-weight:800;text-transform:uppercase;font-size:13px}.ok{background:#143f2b;color:#83efb8}.attention{background:#552a1f;color:#ffc5aa}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}.card{background:#151e28;border:1px solid #273444;border-radius:12px;padding:14px}
.label{font-size:12px;color:#97a7b8;text-transform:uppercase}.value{font-weight:800;margin-top:6px;font-size:22px}
.section{margin:22px 0}h2{font-size:15px;text-transform:uppercase;color:#97a7b8;letter-spacing:.05em;margin-bottom:8px}
.names{background:#151e28;border:1px solid #273444;border-radius:10px;padding:12px;max-height:220px;overflow:auto;font-size:14px;line-height:1.7}
.ambiguous{background:#2a1a12;border:1px solid #6b3a1f;border-radius:10px;padding:12px;color:#ffc5aa;font-size:14px;line-height:1.7}
.form{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin-top:10px}
label{display:block;font-size:12px;color:#97a7b8;margin-bottom:5px}
select,input{padding:9px;border-radius:8px;border:1px solid #415064;background:#0d131a;color:#fff;min-width:220px}
button{padding:10px 16px;border:0;border-radius:9px;background:#f5b821;font-weight:900;cursor:pointer}
#status{margin-left:8px}
</style></head><body><main class="wrap">
<h1>Sqorz Match Report</h1>
<p class="muted">Refreshes automatically. This is the live matching state for whichever class the lineup overlay is currently showing.</p>
<div id="summary"></div>
<div class="grid" id="counts"></div>
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
</main>
<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(){
  const r=await fetch('/api/sqorz/match-report',{cache:'no-store'});
  const d=await r.json();
  const summary=document.querySelector('#summary');
  if(!d.sqorz_enabled){summary.innerHTML='<span class="badge attention">DISABLED</span>';document.querySelector('#counts').innerHTML='';return}
  summary.innerHTML='<span class="badge '+(d.sqorz_reachable?'ok':'attention')+'">'+(d.sqorz_reachable?'REACHABLE':'UNREACHABLE')+'</span> '
    +'<span class="muted">Current class: <strong>'+esc(d.current_class_name||'(none yet -- open the lineup or Director once)')+'</strong>'
    +(d.current_class_alias?' &nbsp;alias &rarr; '+esc(d.current_class_alias):'')+'</span>';
  const counts=(d.report&&d.report.counts)||{};
  const gateChecks=(d.report&&d.report.gate_checks)||{};
  const gateTotal=(gateChecks.agree||0)+(gateChecks.disagree||0);
  const gateRate=gateTotal?Math.round(100*(gateChecks.agree||0)/gateTotal)+'% ('+gateChecks.agree+'/'+gateTotal+')':'—';
  document.querySelector('#counts').innerHTML=['exact','strong','weak','none'].map(k=>
    '<div class="card"><div class="label">'+k+'</div><div class="value">'+esc(counts[k]??0)+'</div></div>').join('')
    +'<div class="card"><div class="label">Match path</div><div class="value" style="font-size:16px">'+esc((d.report&&d.report.class_match_path)||'—')+'</div></div>'
    +'<div class="card"><div class="label">Gate agreement</div><div class="value" style="font-size:16px">'+esc(gateRate)+'</div></div>';
  document.querySelector('#unmatched-bbs').innerHTML=(d.report&&d.report.unmatched_bbs.length?d.report.unmatched_bbs.map(esc).join('<br>'):'<span class="muted">none</span>');
  document.querySelector('#unmatched-sqorz').innerHTML=(d.report&&d.report.unmatched_sqorz.length?d.report.unmatched_sqorz.map(esc).join('<br>'):'<span class="muted">none</span>');
  const ambiguous=(d.report&&d.report.ambiguous_plates)||[];
  document.querySelector('#ambiguous-section').style.display=ambiguous.length?'block':'none';
  document.querySelector('#ambiguous').innerHTML=ambiguous.map(esc).join('<br>');
  const select=document.querySelector('#sqorz-class');
  const current=select.value;
  select.innerHTML='<option value="">— select —</option>'+d.sqorz_classes.map(c=>'<option value="'+esc(c)+'">'+esc(c)+'</option>').join('');
  if(current)select.value=current;
  window.__currentClass=d.current_class_name;
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
document.querySelector('#save').addEventListener('click',()=>save(false));
document.querySelector('#clear').addEventListener('click',()=>save(true));
load();
setInterval(load,3000);
</script>
</body></html>'''
