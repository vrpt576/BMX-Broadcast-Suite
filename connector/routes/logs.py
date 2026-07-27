"""Operational log API and browser viewer."""
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, HTMLResponse

from connector.config import get_settings
from connector.services.logging_service import recent_logs

router = APIRouter(tags=["logs"])


@router.get("/logs")
def logs_api(level: str | None = None, search: str = "", limit: int = Query(200, ge=1, le=1000)) -> dict:
    return {"entries": recent_logs(level=level, search=search, limit=limit)}


@router.get("/logs/download")
def download_log() -> FileResponse:
    settings = get_settings()
    path = Path(settings.log_dir) / "bbs.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    return FileResponse(path, media_type="text/plain", filename="bbs.log")


async def logs_page() -> HTMLResponse:
    return HTMLResponse(LOGS_HTML)


LOGS_HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BBS Logs</title><style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#eef2f6;background:#0d131a}*{box-sizing:border-box}body{margin:0}.wrap{width:min(1200px,94vw);margin:auto;padding:28px 0}.top{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}.controls{display:flex;gap:8px;flex-wrap:wrap}input,select,button,a{font:inherit;border-radius:8px;border:1px solid #405064;padding:9px 11px}input,select{background:#151f2a;color:#fff}button,a{background:#f0b429;color:#101820;font-weight:800;text-decoration:none;cursor:pointer}.log{margin-top:18px;background:#080d12;border:1px solid #273444;border-radius:10px;height:68vh;overflow:auto;padding:10px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.row{display:grid;grid-template-columns:170px 85px 180px 1fr;gap:10px;padding:5px 7px;border-bottom:1px solid #18212b;font-size:13px}.INFO{color:#cbd5df}.WARNING{color:#ffd166}.ERROR,.CRITICAL{color:#ff8080}.DEBUG{color:#8ab4f8}.muted{color:#91a0af}@media(max-width:760px){.row{grid-template-columns:1fr}.row span:nth-child(-n+3){display:inline}}</style></head><body><main class="wrap"><div class="top"><div><h1>BBS Logs</h1><p class="muted">Live operational events, SQL failures, cache use, requests, and operator actions.</p></div><div class="controls"><input id="search" placeholder="Search logs"><select id="level"><option value="">All levels</option><option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select><button id="pause">Pause</button><a href="/api/logs/download">Download</a></div></div><div id="log" class="log"></div></main><script>
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let paused=false;
async function load(){if(paused)return;const p=new URLSearchParams({limit:'500',search:document.querySelector('#search').value,level:document.querySelector('#level').value});const r=await fetch('/api/logs?'+p,{cache:'no-store'});const d=await r.json();const box=document.querySelector('#log');box.innerHTML=d.entries.map(x=>`<div class="row ${esc(x.level)}"><span>${esc(x.timestamp)}</span><strong>${esc(x.level)}</strong><span>${esc(x.logger)}</span><span>${esc(x.message)}</span></div>`).join('');box.scrollTop=box.scrollHeight}
document.querySelector('#pause').onclick=e=>{paused=!paused;e.target.textContent=paused?'Resume':'Pause'};document.querySelector('#search').oninput=load;document.querySelector('#level').onchange=load;load();setInterval(load,1500);
</script></body></html>'''
