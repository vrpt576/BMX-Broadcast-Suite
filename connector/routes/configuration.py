"""Track configuration API and setup page."""

from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse

from connector.config import get_settings
from connector.services.configuration_service import ConfigurationService


router = APIRouter(tags=["configuration"])
service = ConfigurationService()


@router.get("/configuration/public")
def get_public_configuration() -> dict[str, Any]:
    """Return only values required by unauthenticated broadcast overlays."""
    return service.get_broadcast_public(get_settings())


@router.get("/configuration")
def get_configuration() -> dict[str, Any]:
    return service.get_public(get_settings())


@router.put("/configuration")
def save_configuration(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    settings = service.save(payload)
    return {
        "saved": True,
        "configuration": service.get_public(settings),
        "message": (
            "Configuration saved. Restart BBS if host, port, CORS, or "
            "remote-access settings changed."
        ),
    }


async def configuration_page() -> HTMLResponse:
    return HTMLResponse(CONFIG_HTML)


CONFIG_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BBS Configuration</title><style>
:root{font-family:Segoe UI,Arial,sans-serif;background:#0e141b;color:#fff}*{box-sizing:border-box}body{margin:0;padding:28px}.wrap{max-width:1000px;margin:auto}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.card{background:#151e28;border:1px solid #293746;border-radius:12px;padding:18px}label{display:block;font-size:13px;color:#aeb9c5;margin-top:12px}input,select{width:100%;margin-top:5px;padding:10px;border-radius:8px;border:1px solid #415064;background:#0d131a;color:#fff}input[type=checkbox]{width:auto}button{margin-top:18px;padding:12px 18px;border:0;border-radius:9px;background:#f3b61f;font-weight:900}.muted{color:#aeb9c5}.ok{color:#7ee2aa}.error{color:#ff8b8b}@media(max-width:700px){.grid{grid-template-columns:1fr}}
</style></head><body><main class="wrap">
<h1>BBS Track Configuration</h1>
<p class="muted">Settings live in the protected BBS environment file. Passwords and access tokens are never returned to the browser.</p>
<section class="card">
  <h2>Remote admin session</h2>
  <p class="muted">Leave blank on the BBS computer. When remote administration is explicitly enabled, enter its token for this browser tab.</p>
  <label>Admin token<input id="session_admin_token" type="password" autocomplete="off"></label>
  <button id="load">Load configuration</button>
</section>
<div class="grid">
  <section class="card"><h2>Track & Application</h2>
    <label>Track name<input id="track_name"></label><label>Default theme<input id="default_theme"></label>
    <label>Listen host<input id="app_host"></label><label>Listen port<input id="app_port" type="number"></label>
    <label>Public base URL<input id="public_base_url" placeholder="http://bbs-server:8000"></label>
    <label>CORS origins<input id="cors_origins" placeholder="http://trusted-producer:8000"></label>
    <label><input id="remote_control_enabled" type="checkbox"> Allow authenticated remote operator control</label>
    <label>New control token<input id="control_token" type="password" placeholder="Leave blank to keep existing"></label>
    <label><input id="remote_admin_enabled" type="checkbox"> Allow authenticated remote administration</label>
    <label>New admin token<input id="admin_token" type="password" placeholder="Leave blank to keep existing"></label>
  </section>
  <section class="card"><h2>RaceManager SQL</h2>
    <label>SQL host<input id="sql_host"></label><label>Named instance (optional)<input id="sql_instance"></label>
    <label>TCP port (optional)<input id="sql_port" type="number"></label><label>Database<input id="sql_database"></label>
    <label>Login<input id="sql_user"></label><label>Password<input id="sql_password" type="password" placeholder="Leave blank to keep existing"></label>
    <label>ODBC driver<input id="sql_driver"></label><label><input id="sql_encrypt" type="checkbox"> Encrypt connection</label>
    <label><input id="sql_trust_server_certificate" type="checkbox"> Trust server certificate</label>
  </section>
</div>
<button id="save">Save configuration</button> <span id="status" class="muted"></span>
</main><script>
const fields=['track_name','default_theme','app_host','app_port','public_base_url','cors_origins','remote_control_enabled','control_token','remote_admin_enabled','admin_token','sql_host','sql_instance','sql_port','sql_database','sql_user','sql_password','sql_driver','sql_encrypt','sql_trust_server_certificate'];
const sessionToken=document.querySelector('#session_admin_token');
function adminHeaders(extra={}){const headers=new Headers(extra);const token=sessionToken.value.trim();if(token)headers.set('X-BBS-Admin-Token',token);return headers}
async function load(){const status=document.querySelector('#status');status.textContent='Loading…';const response=await fetch('/api/configuration',{cache:'no-store',headers:adminHeaders()});const data=await response.json();if(!response.ok){status.textContent=data.detail||'Configuration unavailable';status.className='error';return}for(const field of fields){const element=document.getElementById(field);if(element.type==='checkbox')element.checked=!!data[field];else element.value=data[field]??''}status.textContent='Configuration loaded.';status.className='ok'}
async function save(){const payload={};for(const field of fields){const element=document.getElementById(field);payload[field]=element.type==='checkbox'?element.checked:element.value}const response=await fetch('/api/configuration',{method:'PUT',headers:adminHeaders({'Content-Type':'application/json'}),body:JSON.stringify(payload)});const data=await response.json();const status=document.querySelector('#status');status.textContent=data.message||data.detail||'Save failed';status.className=response.ok?'ok':'error'}
document.querySelector('#load').addEventListener('click',load);document.querySelector('#save').addEventListener('click',save);load();
</script></body></html>'''
