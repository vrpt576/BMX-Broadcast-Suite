"""First-run Setup wizard: prerequisite installation and the SQL account wizard.

Runs after BBS is installed, not during -- see docs/setup-wizard.md for why
(avoids the WiX Burn bootstrapper pattern that got an earlier BBS release
flagged as malware; see CLAUDE.md's "Windows packaging / antivirus
lessons"). This whole namespace is loopback-only, always, regardless of
BBS_REMOTE_ADMIN_ENABLED or any token -- see connector/security.py's
SETUP_API_PREFIX rule and test_network_security.py's
test_setup_wizard_is_loopback_only_even_with_a_valid_admin_token. It
creates database accounts and installs system-level software; nothing here
is broadcast data.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse

from connector.config import APPLICATION_ROOT, get_settings
from connector.dependencies import (
    get_database,
    get_sql_wizard_plan_cache,
    get_sqorz_service,
)
from connector.routes.diagnostics import get_diagnostics_service
from connector.services import odbc_service, sql_setup_service as sql_setup
from connector.services.configuration_service import ConfigurationService
from connector.services.diagnostics_service import DiagnosticsService
from connector.services.sql_setup_service import PlanCache
from connector.services.sqorz_service import SqorzService
from database.racemanager import RaceManagerDatabase

router = APIRouter(tags=["setup"])


# ---------------------------------------------------------------------------
# Part 3: the consolidated status a track operator lands on
# ---------------------------------------------------------------------------


@router.get("/setup/status")
def setup_status(
    diagnostics: DiagnosticsService = Depends(get_diagnostics_service),
    sqorz: SqorzService = Depends(get_sqorz_service),
) -> dict[str, Any]:
    report = diagnostics.run()
    checks_by_key = {check["key"]: check for check in report["checks"]}
    odbc = odbc_service.detect()
    database_check = checks_by_key.get("database")
    event_check = checks_by_key.get("event")

    return {
        "odbc_driver": {
            "present": odbc.acceptable,
            "preferred_driver": odbc.preferred_driver,
            "installed_drivers": odbc.installed_drivers,
            "fix_it": None if odbc.acceptable else "/setup#odbc",
        },
        "database": {
            "reachable": bool(database_check and database_check["status"] == "ok"),
            "detail": database_check["detail"] if database_check else "Unknown.",
            "fix_it": None if (database_check and database_check["status"] == "ok") else "/setup#sql",
        },
        "racemanager": {
            "readable": bool(event_check and event_check["status"] == "ok"),
            "detail": event_check["detail"] if event_check else "Unknown.",
            "fix_it": None if (event_check and event_check["status"] == "ok") else "/setup#sql",
        },
        "sqorz": {
            "configured": sqorz.enabled,
            "fix_it": None if sqorz.enabled else "/configuration",
        },
    }


# ---------------------------------------------------------------------------
# Part 1: ODBC driver prerequisite
# ---------------------------------------------------------------------------


@router.get("/setup/odbc/license")
def odbc_license() -> FileResponse:
    license_path = odbc_service.bundled_license_path(APPLICATION_ROOT)
    if license_path is None:
        raise HTTPException(404, "The bundled license file is not available in this build.")
    return FileResponse(license_path, media_type="application/rtf", filename="ODBC-Driver-LICENSE.rtf")


@router.post("/setup/odbc/install")
def odbc_install(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if not payload.get("agree"):
        raise HTTPException(
            400,
            "You must agree to the Microsoft license terms (see /api/setup/odbc/license) "
            "before installing.",
        )
    source = payload.get("source")
    if source not in ("bundled", "download"):
        raise HTTPException(400, "source must be 'bundled' or 'download'.")

    try:
        if source == "bundled":
            msi_path = odbc_service.bundled_installer_path(APPLICATION_ROOT)
            if msi_path is None:
                raise HTTPException(
                    409,
                    "No bundled installer is available in this build -- use source: "
                    "'download' instead.",
                )
        else:
            destination = APPLICATION_ROOT / "prerequisites" / "msodbcsql18-x64-downloaded.msi"
            msi_path = odbc_service.download_installer(destination)
        odbc_service.install_from_msi(msi_path)
    except odbc_service.OdbcInstallError as exc:
        raise HTTPException(500, str(exc)) from exc

    status = odbc_service.detect()
    return {
        "installed": status.acceptable,
        "preferred_driver": status.preferred_driver,
        "installed_drivers": status.installed_drivers,
    }


# ---------------------------------------------------------------------------
# Part 2: the SQL read-only account wizard
# ---------------------------------------------------------------------------


def _timeout(settings) -> int:
    # Must stay an int -- pyodbc.connect()'s timeout kwarg maps to a C
    # long (SQL_ATTR_LOGIN_TIMEOUT); a float raises TypeError inside
    # pyodbc itself before any connection attempt happens.
    return int(settings.sql_connect_timeout)


def _require_login_name(raw: str) -> str:
    """Validated immediately after extraction from the request, before any
    connection is attempted -- both so a bad login_name (the testing aid;
    see sql_setup_service's module docstring) fails fast with a clear 400
    instead of wasting a connection attempt, and so sql_setup_service's
    own SqlSetupError never has a chance to surface as an unhandled 500."""
    try:
        return sql_setup.validate_login_name(raw)
    except sql_setup.SqlSetupError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/setup/sql/instances")
def sql_instances() -> dict[str, Any]:
    detected = sql_setup.detect_local_sql_instances()
    default = detected[0] if detected else sql_setup.COMMON_RACEMANAGER_INSTANCE
    return {"detected": detected, "default": default}


def _windows_auth_connect_or_none(
    *, host: str, instance: str, database: str, timeout: int
) -> tuple[Any, str | None]:
    connection_string = sql_setup.windows_auth_connection_string(
        host=host, instance=instance, database=database
    )
    try:
        return sql_setup.connect(connection_string, timeout=timeout), None
    except sql_setup.SqlSetupError as exc:
        return None, str(exc)


@router.post("/setup/sql/preflight")
def sql_preflight(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    host = str(payload.get("host") or "").strip()
    instance = str(payload.get("instance") or "").strip()
    database = str(payload.get("database") or "RACE").strip()
    login_name = _require_login_name(str(payload.get("login_name") or sql_setup.LOGIN_NAME).strip())
    if not host:
        raise HTTPException(400, "host is required.")

    settings = get_settings()
    connection, error = _windows_auth_connect_or_none(
        host=host, instance=instance, database=database, timeout=_timeout(settings)
    )
    try:
        port = int(payload["port"]) if payload.get("port") else None
    except (TypeError, ValueError):
        port = None
    try:
        report = sql_setup.run_preflight(
            connection, connection_error=error, tcp_host=host, tcp_port=port, login_name=login_name
        )
    finally:
        if connection is not None:
            connection.close()

    return {
        "connected_with_windows_auth": report.connected,
        "connection_error": report.connection_error,
        "server_version": report.server_version,
        "integrated_security_only": report.integrated_security_only,
        "tcp_reachable": report.tcp_reachable,
        "existing_login_present": report.existing_login_present,
        "service_account_is_sysadmin": report.service_account_is_sysadmin,
        "blocking_issues": report.blocking_issues,
        "can_run_automatically": report.connected and not report.blocking_issues,
    }


@router.post("/setup/sql/plan")
def sql_plan(
    payload: dict[str, Any] = Body(...),
    cache: PlanCache = Depends(get_sql_wizard_plan_cache),
) -> dict[str, Any]:
    """The same-computer path: BBS opens the Windows-authenticated
    connection itself, so it already knows whether the login exists and
    can offer a precise create-or-reset plan. See /setup/sql/generate for
    the separate-computer path, which never attempts this connection."""
    host = str(payload.get("host") or "").strip()
    instance = str(payload.get("instance") or "").strip()
    database = str(payload.get("database") or "RACE").strip()
    login_name = _require_login_name(str(payload.get("login_name") or sql_setup.LOGIN_NAME).strip())
    if not host:
        raise HTTPException(400, "host is required.")

    settings = get_settings()
    connection, error = _windows_auth_connect_or_none(
        host=host, instance=instance, database=database, timeout=_timeout(settings)
    )
    if connection is None:
        raise HTTPException(
            409,
            f"Could not connect with Windows authentication to plan against: {error}. "
            "If BBS is on a different computer than RaceManager, this is expected -- use "
            "/api/setup/sql/generate instead (or the 'different computer' option on the "
            "Setup page), which does not require this connection.",
        )
    try:
        report = sql_setup.run_preflight(
            connection, tcp_host=host, tcp_port=payload.get("port"), login_name=login_name
        )
        if report.blocking_issues:
            raise HTTPException(409, " ".join(report.blocking_issues))
        plan = (
            sql_setup.build_reset_password_plan(database=database, login_name=login_name)
            if report.existing_login_present
            else sql_setup.build_create_plan(database=database, login_name=login_name)
        )
    finally:
        connection.close()

    plan_id = cache.store(plan, host=host, instance=instance, database=database, login_name=login_name)
    return {"plan_id": plan_id, "kind": plan.kind, "sql": plan.sql}


@router.post("/setup/sql/generate")
def sql_generate(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """The separate-computer path: generates SQL to hand to whoever
    administers the SQL Server, without BBS ever attempting to connect to
    it. This is the expected route whenever BBS runs on a different
    machine than RaceManager (the topology this project's own docs
    recommend) -- BBS's service identity crosses the network as the
    *computer* account there and essentially never has rights to connect,
    so there is nothing for a preflight check to do. Not cached, not
    tied to a plan_id -- there is no "run it for me" for this path, only
    review-and-copy, followed by /setup/sql/verify-and-store once the
    operator has run it themselves.

    reset_password=true asks for the ALTER LOGIN form instead, for an
    operator who already knows the login exists and wants to rotate its
    password -- the default IF NOT EXISTS-guarded create is deliberately
    inert against an existing login rather than resetting it by surprise.
    """
    database = str(payload.get("database") or "RACE").strip()
    login_name = _require_login_name(str(payload.get("login_name") or sql_setup.LOGIN_NAME).strip())
    if payload.get("reset_password"):
        plan = sql_setup.build_reset_password_plan(database=database, login_name=login_name)
    else:
        plan = sql_setup.build_offline_create_plan(database=database, login_name=login_name)
    return {"kind": plan.kind, "sql": plan.sql}


@router.post("/setup/sql/apply")
def sql_apply(
    payload: dict[str, Any] = Body(...),
    cache: PlanCache = Depends(get_sql_wizard_plan_cache),
    database: RaceManagerDatabase = Depends(get_database),
) -> dict[str, Any]:
    plan_id = str(payload.get("plan_id") or "")
    cached = cache.take(plan_id)
    if cached is None:
        raise HTTPException(
            400, "This plan has expired or was already used -- generate a new one and try again."
        )

    settings = get_settings()
    connection, error = _windows_auth_connect_or_none(
        host=cached.host, instance=cached.instance, database=cached.database, timeout=_timeout(settings)
    )
    if connection is None:
        raise HTTPException(
            409,
            f"Could not connect with Windows authentication to run this: {error}. Use the SQL "
            "text you already copied and run it yourself as an administrator instead.",
        )
    try:
        sql_setup.apply_plan(connection, cached.plan)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator, never fatal to BBS
        raise HTTPException(500, f"Running the SQL failed: {exc}") from exc
    finally:
        connection.close()

    return _verify_and_store(
        host=cached.host,
        instance=cached.instance,
        database_name=cached.database,
        password=cached.plan.password,
        login_name=cached.login_name,
        settings=settings,
    )


@router.post("/setup/sql/verify-and-store")
def sql_verify_and_store(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """The manual path: the operator ran the generated SQL themselves
    (SSMS, sqlcmd, their own DBA -- whether from /setup/sql/plan on the
    same-computer path or /setup/sql/generate on the separate-computer
    path) and is pasting the password back to confirm it's ready. This is
    the PRIMARY path whenever BBS runs on a different computer than
    RaceManager, not a fallback for a failed automatic attempt. The
    pasted password is handled exactly like a wizard-generated one: never
    logged (this route's body is never written to any log -- see
    connector/main.py's request_logging middleware, which logs only
    method/path/status/elapsed time), never echoed back in this or any
    other response, never surfaced in /api/diagnostics. Verifies by
    actually connecting and reading a row -- BBS never just trusts "I ran
    it." On success it is written into BBS's own configuration file via
    ConfigurationService (the same plaintext-in-.env storage every other
    BBS secret already uses -- see docs/setup-wizard.md), and
    ConfigurationService.save() clears BBS's cached database connection,
    so BBS switches to using this login, not a Windows-auth/LocalSystem
    connection, for all normal operation from that point on."""
    host = str(payload.get("host") or "").strip()
    instance = str(payload.get("instance") or "").strip()
    database_name = str(payload.get("database") or "RACE").strip()
    login_name = _require_login_name(str(payload.get("login_name") or sql_setup.LOGIN_NAME).strip())
    password = str(payload.get("password") or "")
    if not host or not password:
        raise HTTPException(400, "host and password are required.")
    return _verify_and_store(
        host=host,
        instance=instance,
        database_name=database_name,
        password=password,
        login_name=login_name,
        settings=get_settings(),
    )


def _verify_and_store(
    *, host: str, instance: str, database_name: str, password: str, login_name: str, settings
) -> dict[str, Any]:
    connection_string = sql_setup.sql_auth_connection_string(
        host=host,
        instance=instance,
        database=database_name,
        user=login_name,
        password=password,
    )
    try:
        connection = sql_setup.connect(connection_string, timeout=_timeout(settings))
    except sql_setup.SqlSetupError as exc:
        raise HTTPException(
            409, f"Created, but could not reconnect as {login_name} to verify: {exc}"
        ) from exc
    try:
        proof = sql_setup.verify_login(connection, login_name=login_name)
    except sql_setup.SqlSetupError as exc:
        raise HTTPException(409, str(exc)) from exc
    finally:
        connection.close()

    ConfigurationService().save(
        {
            "sql_host": host,
            "sql_instance": instance,
            "sql_database": database_name,
            "sql_user": login_name,
            "sql_password": password,
        }
    )
    return {"verified": True, "proof": proof}


@router.get("/setup/sql/cleanup")
def sql_cleanup(
    database: str = Query("RACE"), login_name: str = Query(sql_setup.LOGIN_NAME)
) -> dict[str, Any]:
    login_name = _require_login_name(login_name)
    return {"sql": sql_setup.build_cleanup_sql(database=database, login_name=login_name)}


# ---------------------------------------------------------------------------
# The page itself
# ---------------------------------------------------------------------------


async def setup_page() -> HTMLResponse:
    return HTMLResponse(SETUP_HTML)


SETUP_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BBS Setup</title>
<style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#f7f7f7;background:#0e141b}*{box-sizing:border-box}body{margin:0;padding:28px}.wrap{max-width:840px;margin:auto}
.muted{color:#aeb9c5}.badge{padding:6px 12px;border-radius:999px;font-weight:800;text-transform:uppercase;font-size:12px;margin-right:6px;display:inline-block}.ok{background:#143f2b;color:#83efb8}.attention{background:#552a1f;color:#ffc5aa}.neutral{background:#273444;color:#cfd8e3}
.card{background:#151e28;border:1px solid #273444;border-radius:12px;padding:18px;margin:14px 0}
.stepcard{display:flex;align-items:center;justify-content:space-between;gap:12px}
h1{font-size:26px}h2{font-size:17px;margin:0 0 6px}
.label{font-size:12px;color:#97a7b8;text-transform:uppercase;letter-spacing:.04em}
button{padding:9px 16px;border:0;border-radius:9px;background:#f5b821;font-weight:900;cursor:pointer;color:#101820}
button.secondary{background:#273444;color:#f7f7f7}
button:disabled{opacity:.5;cursor:not-allowed}
input,select{padding:9px;border-radius:8px;border:1px solid #415064;background:#0d131a;color:#fff;min-width:200px}
label.field{display:block;font-size:12px;color:#97a7b8;margin:10px 0 4px}
pre{white-space:pre-wrap;word-break:break-word;background:#0d131a;border:1px solid #273444;border-radius:10px;padding:12px;max-height:320px;overflow:auto;font-size:13px}
.issue{background:#2a1a12;border:1px solid #6b3a1f;border-radius:10px;padding:12px;color:#ffc5aa;font-size:14px;line-height:1.6;margin:8px 0}
#status-msg{margin-left:8px;font-size:13px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
a{color:#f5b821}
</style></head><body><main class="wrap">
<h1>BBS Setup</h1>
<p class="muted">Everything BBS needs before it can read RaceManager -- fixed here, once.</p>

<div class="card" id="overview"><h2>Status</h2><div id="overview-body">Checking...</div></div>

<div class="card" id="odbc-card"><a id="odbc"></a><h2>1. SQL Server ODBC Driver</h2>
  <div id="odbc-body">Checking...</div>
  <div id="odbc-install-ui" style="display:none">
    <p class="muted">BBS needs Microsoft's ODBC Driver 18 (or 17) for SQL Server to read RaceManager's database.
    <a href="/api/setup/odbc/license" target="_blank">View Microsoft's license terms</a> -- the entire driver package
    is redistributable under those terms; BBS bundles a copy so this works with no internet at the track.</p>
    <label class="row"><input type="checkbox" id="odbc-agree"> I have reviewed the license and agree to it.</label>
    <div class="row" style="margin-top:10px">
      <button id="odbc-install-bundled" disabled>Install bundled copy (no internet needed)</button>
      <button id="odbc-install-download" class="secondary" disabled>Download latest from Microsoft instead</button>
      <span id="odbc-status-msg" class="muted"></span>
    </div>
  </div>
</div>

<div class="card" id="sql-card"><a id="sql"></a><h2>2. Read-only RaceManager account</h2>
  <div id="sql-body">
    <p class="muted">This creates a SQL Server login called <code>bbs_connector</code> that can only <em>read</em> RaceManager's data. Once it's set up, BBS uses it -- not an administrator account -- for everything it does day to day.</p>

    <label class="field">Is BBS installed on the same computer as RaceManager's SQL Server?</label>
    <div class="row">
      <button id="topology-same" class="secondary">Yes, same computer</button>
      <button id="topology-different" class="secondary">No, a different computer</button>
    </div>
    <p class="muted" style="margin-top:8px">Not sure? If BBS runs on a dedicated broadcast PC, or is reached over a network like Tailscale, choose "a different computer" -- that's a normal, expected setup, not something to fix.</p>

    <div id="sql-fields" style="display:none">
      <label class="field">SQL Server host</label><input id="sql-host" value="localhost">
      <label class="field">Instance (leave blank for a default instance)</label><input id="sql-instance" list="sql-instance-list">
      <datalist id="sql-instance-list"></datalist>
      <label class="field">Database</label><input id="sql-database" value="RACE">

      <div id="sql-same-pc-ui" style="display:none">
        <div class="row" style="margin-top:12px">
          <button id="sql-preflight">Check connection automatically</button>
          <span id="sql-preflight-msg" class="muted"></span>
        </div>
        <div id="sql-sysadmin-note" class="issue" style="display:none;background:#182636;border-color:#2c4863;color:#bcd6ee"></div>
      </div>

      <div id="sql-issues"></div>

      <div id="sql-generate-ui" style="display:none">
        <p class="muted" id="sql-generate-intro">BBS did not connect to generate this -- that's expected here. Hand the SQL below to whoever administers this SQL Server.</p>
        <div class="row">
          <button id="sql-generate">Generate the SQL</button>
          <label class="row" style="font-size:13px;font-weight:normal"><input type="checkbox" id="sql-generate-reset"> This login already exists -- generate a password reset instead</label>
        </div>
      </div>

      <div id="sql-plan-area" style="display:none">
        <h2 style="margin-top:18px">Review before anything runs</h2>
        <p class="muted" id="sql-plan-intro">This is the exact SQL that will run. Copy it to hand to whoever administers this SQL Server.</p>
        <pre id="sql-plan-text"></pre>
        <div class="row">
          <button id="sql-copy" class="secondary">Copy SQL</button>
          <button id="sql-run-auto" style="display:none">Run it for me</button>
          <span id="sql-apply-msg" class="muted"></span>
        </div>
        <div id="sql-manual-area" style="margin-top:14px">
          <p class="muted">Once this SQL has run -- by BBS automatically, by you, or by your DBA -- paste the password shown above back here and BBS will verify it and save it.</p>
          <div class="row">
            <input id="sql-manual-password" placeholder="password from the SQL above" style="min-width:280px">
            <button id="sql-manual-verify" class="secondary">Verify and save</button>
          </div>
        </div>
      </div>
    </div>

    <details style="margin-top:16px"><summary class="muted">Undo this later</summary>
      <p class="muted">Run this on the SQL Server to remove the account BBS created:</p>
      <pre id="sql-cleanup-text">Loading...</pre>
    </details>
  </div>
</div>

<div class="card"><h2>3. Sqorz live timing (optional)</h2>
  <p class="muted">Not required. <a href="/configuration">Configure it</a> if your track uses Sqorz.
  See <a href="/sqorz-status">Sqorz status</a> once it's set up.</p>
</div>

<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let currentPlanId=null, currentPlanSql=null;

async function loadStatus(){
  const r=await fetch('/api/setup/status',{cache:'no-store'});
  const d=await r.json();
  const badge=(ok)=>'<span class="badge '+(ok?'ok':'attention')+'">'+(ok?'OK':'NEEDS ATTENTION')+'</span>';
  document.querySelector('#overview-body').innerHTML=
    '<div class="row">'+badge(d.odbc_driver.present)+' ODBC driver</div>'
    +'<div class="row" style="margin-top:6px">'+badge(d.database.reachable)+' Database connection -- '+esc(d.database.detail)+'</div>'
    +'<div class="row" style="margin-top:6px">'+badge(d.racemanager.readable)+' RaceManager data -- '+esc(d.racemanager.detail)+'</div>'
    +'<div class="row" style="margin-top:6px">'+badge(d.sqorz.configured)+' Sqorz live timing (optional)</div>';

  const odbcBody=document.querySelector('#odbc-body');
  if(d.odbc_driver.present){
    odbcBody.innerHTML='<span class="badge ok">FOUND</span> '+esc(d.odbc_driver.preferred_driver);
    document.querySelector('#odbc-install-ui').style.display='none';
  } else {
    odbcBody.innerHTML='<span class="badge attention">NOT FOUND</span> Installed drivers: '+esc(d.odbc_driver.installed_drivers.join(', ')||'none');
    document.querySelector('#odbc-install-ui').style.display='block';
  }
  return d;
}

document.querySelector('#odbc-agree').addEventListener('change', (e)=>{
  document.querySelector('#odbc-install-bundled').disabled=!e.target.checked;
  document.querySelector('#odbc-install-download').disabled=!e.target.checked;
});

async function installOdbc(source){
  const msg=document.querySelector('#odbc-status-msg');
  msg.textContent='Installing...';
  try{
    const r=await fetch('/api/setup/odbc/install',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source, agree:true})});
    const d=await r.json();
    if(!r.ok){msg.textContent=d.detail||'Failed.';return}
    msg.textContent=d.installed?'Installed successfully.':'Ran, but the driver still is not detected -- a restart may be required.';
    loadStatus();
  }catch(e){msg.textContent='Failed: '+esc(e)}
}
document.querySelector('#odbc-install-bundled').addEventListener('click',()=>installOdbc('bundled'));
document.querySelector('#odbc-install-download').addEventListener('click',()=>installOdbc('download'));

async function loadInstances(){
  const r=await fetch('/api/setup/sql/instances',{cache:'no-store'});
  const d=await r.json();
  document.querySelector('#sql-instance-list').innerHTML=d.detected.map(i=>'<option value="'+esc(i)+'">').join('');
  if(!document.querySelector('#sql-instance').value) document.querySelector('#sql-instance').value=d.default;
}

function sqlParams(){
  return {
    host: document.querySelector('#sql-host').value.trim(),
    instance: document.querySelector('#sql-instance').value.trim(),
    database: document.querySelector('#sql-database').value.trim()||'RACE',
  };
}

function selectTopology(mode){
  document.querySelector('#sql-fields').style.display='block';
  document.querySelector('#sql-same-pc-ui').style.display = mode==='same' ? 'block' : 'none';
  document.querySelector('#sql-generate-ui').style.display = mode==='different' ? 'block' : 'none';
  document.querySelector('#sql-issues').innerHTML='';
  document.querySelector('#sql-sysadmin-note').style.display='none';
  document.querySelector('#sql-plan-area').style.display='none';
  document.querySelector('#sql-preflight-msg').textContent='';
  const hostInput=document.querySelector('#sql-host');
  if(mode==='different'){
    // "localhost" would point BBS's own verification step at itself, not
    // at RaceManager's machine -- that default is actively wrong here.
    if(hostInput.value.trim()==='localhost') hostInput.value='';
    hostInput.placeholder='hostname or IP of the RaceManager computer';
  } else {
    if(!hostInput.value.trim()) hostInput.value='localhost';
    hostInput.placeholder='';
  }
}
document.querySelector('#topology-same').addEventListener('click', ()=>selectTopology('same'));
document.querySelector('#topology-different').addEventListener('click', ()=>selectTopology('different'));

document.querySelector('#sql-preflight').addEventListener('click', async ()=>{
  const msg=document.querySelector('#sql-preflight-msg');
  const issues=document.querySelector('#sql-issues');
  const sysadminNote=document.querySelector('#sql-sysadmin-note');
  msg.textContent='Checking...'; issues.innerHTML=''; sysadminNote.style.display='none';
  document.querySelector('#sql-plan-area').style.display='none';
  document.querySelector('#sql-generate-ui').style.display='none';
  const r=await fetch('/api/setup/sql/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(sqlParams())});
  const d=await r.json();
  if(!d.connected_with_windows_auth){
    msg.textContent="Couldn't connect automatically -- that can happen even on the same computer, depending on what account BBS's service runs under. Use \"Generate the SQL\" below instead.";
    document.querySelector('#sql-generate-ui').style.display='block';
    return;
  }
  msg.textContent='Connected'+(d.server_version?(' -- '+esc(d.server_version)):'')+(d.existing_login_present?' (bbs_connector already exists -- will offer a password reset).':' (bbs_connector does not exist yet -- will offer to create it).');
  if(d.service_account_is_sysadmin===true){
    sysadminNote.style.display='block';
    sysadminNote.textContent="Note: the account BBS is running as currently has sysadmin rights on this SQL Server. That's this SQL Server's own configuration, not something BBS controls -- but it means your scoring database currently trusts BBS's service account more broadly than it needs to. Once this wizard finishes, BBS switches to using the new read-only bbs_connector login for everything it does day to day, regardless.";
  }
  (d.blocking_issues||[]).forEach(issue=>{const el=document.createElement('div');el.className='issue';el.textContent=issue;issues.append(el)});
  if(d.can_run_automatically){
    await requestPlan();
  } else {
    document.querySelector('#sql-generate-ui').style.display='block';
  }
});

async function requestPlan(){
  const r=await fetch('/api/setup/sql/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(sqlParams())});
  const d=await r.json();
  if(!r.ok){document.querySelector('#sql-preflight-msg').textContent=d.detail||'Could not generate a plan.';return}
  currentPlanId=d.plan_id; currentPlanSql=d.sql;
  document.querySelector('#sql-plan-text').textContent=d.sql;
  document.querySelector('#sql-plan-intro').textContent="This is the exact SQL that will run. Copy it to hand to whoever administers this SQL Server if you'd rather run it yourself.";
  document.querySelector('#sql-run-auto').style.display='inline-block';
  document.querySelector('#sql-plan-area').style.display='block';
}

document.querySelector('#sql-generate').addEventListener('click', async ()=>{
  const resetPassword=document.querySelector('#sql-generate-reset').checked;
  const body={...sqlParams(), reset_password: resetPassword};
  const r=await fetch('/api/setup/sql/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(!r.ok){return}
  currentPlanId=null; currentPlanSql=d.sql;
  document.querySelector('#sql-plan-text').textContent=d.sql;
  document.querySelector('#sql-plan-intro').textContent=resetPassword
    ? 'This resets the password for an existing bbs_connector login. Hand it to whoever administers this SQL Server.'
    : "This safely creates bbs_connector only if it doesn't already exist -- running it against an existing login changes nothing. Hand it to whoever administers this SQL Server.";
  document.querySelector('#sql-run-auto').style.display='none';
  document.querySelector('#sql-plan-area').style.display='block';
});

document.querySelector('#sql-copy').addEventListener('click', async ()=>{
  try{await navigator.clipboard.writeText(currentPlanSql||'')}catch(e){}
});

document.querySelector('#sql-run-auto').addEventListener('click', async ()=>{
  const msg=document.querySelector('#sql-apply-msg');
  msg.textContent='Running...';
  const body={plan_id: currentPlanId, ...sqlParams()};
  const r=await fetch('/api/setup/sql/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(!r.ok){msg.textContent=d.detail||'Failed.';return}
  msg.textContent='Verified: read a row from '+esc(d.proof.read_a_row_from)+'. Credentials saved.';
  loadStatus();
});

document.querySelector('#sql-manual-verify').addEventListener('click', async ()=>{
  const msg=document.querySelector('#sql-apply-msg');
  const password=document.querySelector('#sql-manual-password').value;
  msg.textContent='Verifying...';
  const body={...sqlParams(), password};
  const r=await fetch('/api/setup/sql/verify-and-store',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(!r.ok){msg.textContent=d.detail||'Failed.';return}
  msg.textContent='Verified: read a row from '+esc(d.proof.read_a_row_from)+'. Credentials saved.';
  document.querySelector('#sql-manual-password').value='';
  loadStatus();
});

async function loadCleanup(){
  const r=await fetch('/api/setup/sql/cleanup?database='+encodeURIComponent(sqlParams().database||'RACE'));
  const d=await r.json();
  document.querySelector('#sql-cleanup-text').textContent=d.sql;
}

loadStatus();
loadInstances();
loadCleanup();
</script>
</body></html>'''
