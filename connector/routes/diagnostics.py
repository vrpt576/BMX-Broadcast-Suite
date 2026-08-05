"""Installation and diagnostics API/page."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from connector.config import get_settings
from connector.dependencies import get_database, get_race_program_export_service
from connector.models import RaceProgramStructureExport
from connector.services.diagnostics_service import DiagnosticsService
from connector.services.race_program_export_service import RaceProgramExportService
from database.racemanager import RaceManagerDatabase

router = APIRouter(tags=["diagnostics"])


def get_diagnostics_service(database: RaceManagerDatabase = Depends(get_database)) -> DiagnosticsService:
    return DiagnosticsService(get_settings(), database)


@router.get("/diagnostics")
def diagnostics(service: DiagnosticsService = Depends(get_diagnostics_service)) -> dict:
    return service.run()


@router.get(
    "/diagnostics/race-program/export",
    response_model=RaceProgramStructureExport,
)
def race_program_export(
    motoboard_id: UUID | None = Query(
        default=None,
        description="Defaults to the newest RaceManager event.",
    ),
    service: RaceProgramExportService = Depends(get_race_program_export_service),
) -> RaceProgramStructureExport:
    """Export event structure without rider or connector personal data."""
    return service.export(motoboard_id)


async def diagnostics_page() -> HTMLResponse:
    return HTMLResponse(DIAGNOSTICS_HTML)


DIAGNOSTICS_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BBS Diagnostics</title>
<style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#f7f7f7;background:#0e141b}*{box-sizing:border-box}body{margin:0;padding:28px}.wrap{max-width:1050px;margin:auto}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.muted{color:#aeb9c5}.badge{padding:8px 12px;border-radius:999px;font-weight:800;text-transform:uppercase}.ok{background:#143f2b;color:#83efb8}.attention{background:#552a1f;color:#ffc5aa}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:22px 0}.card{background:#151e28;border:1px solid #273444;border-radius:12px;padding:16px}.label{font-size:12px;color:#97a7b8;text-transform:uppercase}.value{font-weight:750;margin-top:6px;overflow-wrap:anywhere}.checks{display:grid;gap:10px}.check{display:grid;grid-template-columns:130px 220px 1fr;gap:14px;align-items:center;background:#151e28;border:1px solid #273444;border-radius:10px;padding:13px}.status{font-weight:900;text-transform:uppercase}.status-ok{color:#75e3aa}.status-warning{color:#ffc857}.status-error{color:#ff7b7b}button{background:#f5b821;border:0;border-radius:9px;padding:11px 17px;font-weight:900;cursor:pointer}code{background:#0b1016;padding:2px 6px;border-radius:5px}@media(max-width:700px){.check{grid-template-columns:1fr}.top{display:block}button{margin-top:12px}}</style>
</head><body><main class="wrap"><div class="top"><div><h1>BBS Installation Diagnostics</h1><p class="muted">Checks the connector runtime, SQL driver, configuration, network path, database login, and active RaceManager event.</p></div><button id="run">Run checks</button></div><div id="summary"></div><section class="grid" id="config"></section><section class="checks" id="checks" aria-live="polite"></section></main>
<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function run(){document.querySelector('#checks').innerHTML='<div class="card">Running diagnostics…</div>';try{const r=await fetch('/api/diagnostics',{cache:'no-store'});const d=await r.json();render(d)}catch(e){document.querySelector('#checks').innerHTML='<div class="card status-error">Diagnostics request failed: '+esc(e)+'</div>'}}
function render(d){document.querySelector('#summary').innerHTML='<span class="badge '+esc(d.status)+'">'+esc(d.status)+'</span><span class="muted"> &nbsp;Checked '+esc(new Date(d.checked_at).toLocaleString())+'</span>';const c=d.configuration,a=d.application;document.querySelector('#config').innerHTML=[['Version',a.version],['Platform',a.platform],['SQL server',c.sql_server],['Database',c.sql_database],['Login',c.sql_user],['ODBC driver',c.sql_driver],['Password configured',c.password_configured?'Yes':'No'],['State file',c.state_file]].map(x=>'<div class="card"><div class="label">'+esc(x[0])+'</div><div class="value">'+esc(x[1])+'</div></div>').join('');document.querySelector('#checks').innerHTML=d.checks.map(x=>'<article class="check"><div class="status status-'+esc(x.status)+'">'+esc(x.status)+'</div><strong>'+esc(x.label)+'</strong><div class="muted">'+esc(x.detail)+'</div></article>').join('')}
document.querySelector('#run').addEventListener('click',run);run();
</script></body></html>'''
