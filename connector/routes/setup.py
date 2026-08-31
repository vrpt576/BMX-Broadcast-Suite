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

Written for a track operator, not a DBA -- see docs/setup-wizard.md and
this module's own SETUP_HTML for the reasoning: the primary path
(sql_admin_setup()) asks for a SQL Server administrator's username and
password and does everything itself, because handing an operator a T-SQL
script to run is not a reasonable ask of someone whose job is running a
BMX track, not a database.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse

from connector.config import APPLICATION_ROOT, get_settings
from connector.dependencies import get_sqorz_service
from connector.routes.diagnostics import get_diagnostics_service
from connector.services import odbc_service, sql_setup_service as sql_setup
from connector.services.configuration_service import ConfigurationService
from connector.services.diagnostics_service import DiagnosticsService
from connector.services.sqorz_service import SqorzService

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
    settings = get_settings()

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
            "sql_user": settings.sql_user,
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
# Part 2: connecting BBS to RaceManager
# ---------------------------------------------------------------------------


def _timeout(settings) -> int:
    # Must stay an int -- pyodbc.connect()'s timeout kwarg maps to a C
    # long (SQL_ATTR_LOGIN_TIMEOUT); a float raises TypeError inside
    # pyodbc itself before any connection attempt happens.
    return int(settings.sql_connect_timeout)


def _parse_port(payload: dict[str, Any]) -> int | None:
    try:
        return int(payload["port"]) if payload.get("port") else None
    except (TypeError, ValueError):
        return None


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


@router.post("/setup/sql/discover")
def sql_discover(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """"Find it for me": asks the target host's SQL Server Browser
    service (UDP 1434) which instance to use and what port it's
    listening on, rather than making the operator go find that out
    themselves -- see sql_setup.discover_via_browser_service for why this
    is the right way to ask (a single UDP query, not a port scan). If the
    Browser service doesn't answer (it's frequently disabled), falls back
    to checking the one universally standard SQL Server port (1433) --
    still not a scan -- and says plainly, either way, when it couldn't
    fully confirm the answer."""
    host = str(payload.get("host") or "").strip()
    if not host:
        raise HTTPException(400, "A SQL Server address is required.")

    instances = sql_setup.discover_via_browser_service(host)
    if instances:
        selected = next(
            (i for i in instances if i["instance"].upper() == sql_setup.COMMON_RACEMANAGER_INSTANCE),
            instances[0],
        )
        return {"found": True, "via": "browser", "instances": instances, "selected": selected}

    if sql_setup.probe_default_sql_port(host):
        return {
            "found": True,
            "via": "fallback",
            "instances": [],
            "selected": {"instance": "", "port": 1433, "version": None},
            "message": "The SQL Server Browser service didn't respond, so the instance name couldn't "
            "be confirmed -- but something is listening on the standard SQL Server port (1433), filled "
            "in below. If that's not right, ask whoever administers this SQL Server for the exact "
            "instance name and port.",
        }

    return {
        "found": False,
        "via": "none",
        "instances": [],
        "selected": None,
        "message": "The SQL Server Browser service didn't respond, and nothing answered on the "
        "standard SQL Server port either. Enter the instance name and port yourself if you know "
        "them, or ask whoever administers this SQL Server.",
    }


def _create_or_reset_login(
    connection: Any, *, database: str, login_name: str
) -> sql_setup.Plan | None:
    """Shared by the automatic and admin-credentials paths once a
    connection is open: checks the connected account can manage logins,
    returning None rather than raising if not (each caller reports that
    differently), then detects whether login_name already exists, builds
    the matching plan, and runs it."""
    if not sql_setup.check_login_management_rights(connection):
        return None
    existing = sql_setup.login_exists(connection, login_name)
    plan = (
        sql_setup.build_reset_password_plan(database=database, login_name=login_name)
        if existing
        else sql_setup.build_create_plan(database=database, login_name=login_name)
    )
    sql_setup.apply_plan(connection, plan)
    return plan


@router.post("/setup/sql/auto-setup")
def sql_auto_setup(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Option 1, tried first: free, and needs nothing typed. Tries BBS's
    own Windows service identity against `localhost` -- on a single-PC
    track (one computer running RaceManager and everything else, the most
    common small-track setup), the SQL Server is local and that identity
    is frequently already a sysadmin there, so this alone is often enough
    to finish with one click and nothing typed.

    If it can't connect, or connects but the account can't manage logins,
    that is reported here as a normal outcome (never a 4xx/5xx) for the
    page to fall through from calmly into asking for administrator
    credentials instead (see sql_admin_setup) -- it does NOT mean
    anything is wrong; it commonly just means BBS is on a different
    computer than RaceManager's SQL Server, or that this computer's own
    identity isn't a SQL Server administrator here.
    """
    host = str(payload.get("host") or "localhost").strip()
    instance = str(payload.get("instance") or "").strip()
    database = str(payload.get("database") or "RACE").strip()
    port = _parse_port(payload)
    login_name = _require_login_name(str(payload.get("login_name") or sql_setup.LOGIN_NAME).strip())

    settings = get_settings()
    connection_string = sql_setup.windows_auth_connection_string(
        host=host, instance=instance, database=database, port=port
    )
    try:
        connection = sql_setup.connect(connection_string, timeout=_timeout(settings))
    except sql_setup.SqlSetupError:
        return {"automatic": False, "reason": "could_not_connect"}

    try:
        plan = _create_or_reset_login(connection, database=database, login_name=login_name)
        if plan is None:
            return {"automatic": False, "reason": "insufficient_rights"}
    except Exception:  # noqa: BLE001 - a normal, expected outcome to fall through from
        return {"automatic": False, "reason": "setup_failed"}
    finally:
        connection.close()

    result = _verify_and_store(
        host=host,
        instance=instance,
        database_name=database,
        password=plan.password,
        login_name=login_name,
        port=port,
        settings=settings,
    )
    result["automatic"] = True
    result["created"] = plan.kind == "create"
    return result


def _probe_mixed_mode_disabled(*, host: str, instance: str, database: str, port: int | None, settings) -> bool:
    """Best-effort diagnostic, run only after a SQL-auth admin connection
    attempt has already failed: tries a lightweight Windows-auth
    connection (BBS's own service identity) solely to check whether
    mixed-mode authentication is off, which would explain that failure
    regardless of which SQL credentials were typed in -- retrying with
    different admin credentials there would never work. Never used to
    perform any setup work. If even this can't connect, or the property
    can't be read, returns False (couldn't confirm -- the generic
    connection-failure message is the honest one) rather than guessing
    from the SQL-auth attempt's error text, which does not reliably
    reveal the reason a login was refused."""
    try:
        diagnostic_connection = sql_setup.connect(
            sql_setup.windows_auth_connection_string(
                host=host, instance=instance, database=database, port=port
            ),
            timeout=_timeout(settings),
        )
    except sql_setup.SqlSetupError:
        return False
    try:
        return sql_setup.integrated_security_only(diagnostic_connection) is True
    except Exception:  # noqa: BLE001 - diagnostic only, never fatal
        return False
    finally:
        diagnostic_connection.close()


@router.post("/setup/sql/admin-setup")
def sql_admin_setup(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Option 2, offered when option 1 (sql_auto_setup) didn't pan out:
    the operator supplies a SQL Server *administrator* login's username
    and password. BBS connects as that account -- SQL authentication
    only; there is no way for pyodbc to authenticate as an arbitrary
    Windows account from typed credentials, so this is not offered as an
    option. Unlike option 1, this works whether BBS and RaceManager's SQL
    Server share a computer or not, since SQL authentication doesn't
    depend on machine identity the way Windows authentication does.

    The admin credentials are used only for this one request, held only
    in memory, and never appear in a log, a diagnostic, or a response --
    see connector/main.py's request_logging middleware (method/path/
    status/timing only, never a request body) and the fact that nothing
    below ever writes admin_user or admin_password anywhere but into the
    one connection string used to connect.
    """
    host = str(payload.get("host") or "").strip()
    instance = str(payload.get("instance") or "").strip()
    database = str(payload.get("database") or "RACE").strip()
    port = _parse_port(payload)
    admin_user = str(payload.get("admin_user") or "").strip()
    admin_password = str(payload.get("admin_password") or "")
    login_name = _require_login_name(str(payload.get("login_name") or sql_setup.LOGIN_NAME).strip())
    if not host or not admin_user or not admin_password:
        raise HTTPException(400, "The SQL Server address, administrator username, and administrator password are all required.")

    settings = get_settings()
    admin_connection_string = sql_setup.sql_auth_connection_string(
        host=host, instance=instance, database=database, user=admin_user, password=admin_password, port=port
    )
    try:
        admin_connection = sql_setup.connect(admin_connection_string, timeout=_timeout(settings))
    except sql_setup.SqlSetupError as exc:
        if _probe_mixed_mode_disabled(host=host, instance=instance, database=database, port=port, settings=settings):
            raise HTTPException(
                409,
                {
                    "message": "This SQL Server only accepts Windows logins, so BBS cannot "
                    "create the account this way -- no username and password will work here. "
                    "Either install BBS on the same computer as RaceManager's SQL Server (so "
                    "the automatic option above can sign in with Windows instead), or use "
                    "\"Prefer to have someone else run this?\" below and have your DBA run it "
                    "as a Windows-authenticated administrator.",
                },
            ) from exc
        raise HTTPException(
            409,
            {
                "message": f"Couldn't connect as '{admin_user}'. Double-check the SQL Server "
                "address, username, and password.",
                "technical_detail": str(exc),
            },
        ) from exc

    try:
        plan = _create_or_reset_login(admin_connection, database=database, login_name=login_name)
        if plan is None:
            raise HTTPException(
                409,
                {
                    "message": f"Connected as '{admin_user}', but that account doesn't have "
                    "permission to create or manage logins on this SQL Server. Ask whoever "
                    "administers it to grant that account 'ALTER ANY LOGIN' (or make it a "
                    "sysadmin), or use one of the other options on this page instead.",
                },
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator, never fatal to BBS
        raise HTTPException(
            500, {"message": "Setting this up failed.", "technical_detail": str(exc)}
        ) from exc
    finally:
        admin_connection.close()

    result = _verify_and_store(
        host=host,
        instance=instance,
        database_name=database,
        password=plan.password,
        login_name=login_name,
        port=port,
        settings=settings,
    )
    result["created"] = plan.kind == "create"
    return result


@router.post("/setup/sql/generate")
def sql_generate(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """The "hand it to someone else" path: generates SQL for a track's own
    DBA or IT support to run, without BBS ever connecting to anything.
    Not cached, no apply step -- review-and-copy only, followed by
    /setup/sql/verify-and-store once whoever ran it is done.

    reset_password=true asks for the ALTER LOGIN form instead, for
    someone who already knows the login exists and wants to rotate its
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


@router.post("/setup/sql/verify-and-store")
def sql_verify_and_store(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """"I already have the password": the operator already has a working
    login (their own DBA ran the script, or one already existed) and
    wants BBS to start using it -- no SQL runs here at all, only a
    connection-and-read-a-row check. Also what /setup/sql/admin-setup
    calls internally once it has finished creating or resetting the
    login itself.

    The pasted password is handled exactly like a generated one: never
    logged (this route's body is never written to any log -- see
    connector/main.py's request_logging middleware, which logs only
    method/path/status/elapsed time), never echoed back in this or any
    other response, never surfaced in /api/diagnostics. Verifies by
    actually connecting and reading a row -- BBS never just trusts "I ran
    it" or "it already works." On success it is written into BBS's own
    configuration file via ConfigurationService (the same plaintext-in-
    .env storage every other BBS secret already uses -- see
    docs/setup-wizard.md), and ConfigurationService.save() clears BBS's
    cached database connection, so BBS switches to using this login for
    all normal operation from that point on."""
    host = str(payload.get("host") or "").strip()
    instance = str(payload.get("instance") or "").strip()
    database_name = str(payload.get("database") or "RACE").strip()
    port = _parse_port(payload)
    login_name = _require_login_name(str(payload.get("login_name") or sql_setup.LOGIN_NAME).strip())
    password = str(payload.get("password") or "")
    if not host or not password:
        raise HTTPException(400, "The SQL Server address and password are both required.")
    return _verify_and_store(
        host=host,
        instance=instance,
        database_name=database_name,
        password=password,
        login_name=login_name,
        port=port,
        settings=get_settings(),
    )


def _verify_and_store(
    *, host: str, instance: str, database_name: str, password: str, login_name: str,
    port: int | None = None, settings,
) -> dict[str, Any]:
    connection_string = sql_setup.sql_auth_connection_string(
        host=host,
        instance=instance,
        database=database_name,
        user=login_name,
        password=password,
        port=port,
    )
    try:
        connection = sql_setup.connect(connection_string, timeout=_timeout(settings))
    except sql_setup.SqlSetupError as exc:
        raise HTTPException(
            409,
            {
                "message": f"Couldn't connect as '{login_name}'. Double-check the SQL Server "
                "address and password.",
                "technical_detail": str(exc),
            },
        ) from exc
    try:
        proof = sql_setup.verify_login(connection, login_name=login_name)
    except sql_setup.SqlSetupError as exc:
        raise HTTPException(
            409,
            {
                "message": f"Connected as '{login_name}', but couldn't read RaceManager data "
                "to confirm it works.",
                "technical_detail": str(exc),
            },
        ) from exc
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
.option{background:#101820;border:1px solid #2b3948;border-radius:10px;padding:16px;margin:14px 0}
.stepcard{display:flex;align-items:center;justify-content:space-between;gap:12px}
h1{font-size:26px}h2{font-size:17px;margin:0 0 6px}h3{font-size:15px;margin:0 0 6px}
.label{font-size:12px;color:#97a7b8;text-transform:uppercase;letter-spacing:.04em}
button{padding:9px 16px;border:0;border-radius:9px;background:#f5b821;font-weight:900;cursor:pointer;color:#101820}
button.secondary{background:#273444;color:#f7f7f7}
button:disabled{opacity:.5;cursor:not-allowed}
input,select{padding:9px;border-radius:8px;border:1px solid #415064;background:#0d131a;color:#fff;min-width:200px}
label.field{display:block;font-size:12px;color:#97a7b8;margin:10px 0 4px}
.fieldhelp{font-size:12px;color:#7f8ea0;margin:2px 0 0}
.promise{font-size:12px;color:#9fd6b0;background:#122a1d;border:1px solid #1f4b30;border-radius:8px;padding:8px 10px;margin:10px 0}
pre{white-space:pre-wrap;word-break:break-word;background:#0d131a;border:1px solid #273444;border-radius:10px;padding:12px;max-height:320px;overflow:auto;font-size:13px}
.issue{background:#2a1a12;border:1px solid #6b3a1f;border-radius:10px;padding:12px;color:#ffc5aa;font-size:14px;line-height:1.6;margin:8px 0}
.success{background:#122a1d;border:1px solid #1f4b30;border-radius:10px;padding:12px;color:#9fd6b0;font-size:14px;line-height:1.6;margin:8px 0}
.detail{font-size:12px;color:#7f8ea0;margin-top:4px}
#status-msg{margin-left:8px;font-size:13px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
a{color:#f5b821}
details summary{cursor:pointer;font-weight:700;padding:4px 0}
.trouble dt{font-weight:800;margin-top:10px;color:#ffc5aa}.trouble dd{margin:2px 0 0;color:#cfd8e3}
.card.skipped{opacity:.5}
.card.skipped::before{content:"Not required for Sqorz-only mode";display:block;color:#9fd6b0;font-weight:800;font-size:12px;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}
</style></head><body><main class="wrap">
<h1>BBS Setup</h1>
<p class="muted">Everything BBS needs before it can read RaceManager -- fixed here, once.</p>

<div class="card" id="mode-card">
  <div class="row" style="justify-content:space-between">
    <div>Mode: <b id="mode-value">—</b> <span id="mode-reason" class="muted"></span></div>
    <button id="mode-recheck" class="secondary">Re-check</button>
  </div>
  <p class="fieldhelp" id="mode-recheck-detail"></p>
</div>

<div class="card" id="overview"><h2>Status</h2><div id="overview-body">Checking...</div>
  <p class="muted" style="margin-top:10px">Don't use RaceManager at this track? <a href="#" id="skip-to-sqorz">Skip straight to Sqorz live timing</a> -- the SQL Server driver and RaceManager connection below aren't required for Sqorz-only operation.</p>
</div>

<div class="card" id="odbc-card"><a id="odbc"></a><h2>1. SQL Server driver</h2>
  <div id="odbc-body">Checking...</div>
  <div id="odbc-install-ui" style="display:none">
    <p class="muted">BBS needs a piece of software from Microsoft (called Driver 18) to talk to RaceManager's database at all.
    <a href="/api/setup/odbc/license" target="_blank">View Microsoft's license terms</a> -- BBS bundles a copy so this works with no internet at the track.</p>
    <label class="row"><input type="checkbox" id="odbc-agree"> I have reviewed the license and agree to it.</label>
    <div class="row" style="margin-top:10px">
      <button id="odbc-install-bundled" disabled>Install bundled copy (no internet needed)</button>
      <button id="odbc-install-download" class="secondary" disabled>Download latest from Microsoft instead</button>
      <span id="odbc-status-msg" class="muted"></span>
    </div>
  </div>
</div>

<div class="card" id="sql-card"><a id="sql"></a><h2>2. Connect BBS to RaceManager</h2>

  <div id="sql-already-done" style="display:none">
    <p class="success" id="sql-already-done-text"></p>
    <button id="sql-change-this" class="secondary">Change this</button>
  </div>

  <div id="sql-full-section">
    <p class="muted">BBS needs its own way to read race data from RaceManager -- separate from your own login, and unable to change anything. BBS will try the easiest option first and only ask for more if it needs to.</p>

    <div class="option" id="auto-setup-option">
      <h3>Set it up automatically</h3>
      <p class="muted">If BBS is installed on the same computer as RaceManager, this often works with nothing else needed.</p>
      <div class="row" style="margin-top:10px">
        <button id="auto-setup-btn">Set it up automatically</button>
        <span id="auto-setup-msg" class="muted"></span>
      </div>
    </div>

    <div class="option" id="admin-setup-option" style="display:none">
      <h3>Enter administrator credentials</h3>
      <p class="muted" id="admin-setup-intro">Enter the username and password for a SQL Server <b>administrator</b> account -- not <code>bbs_connector</code>, and not your own Windows login. BBS uses it once to set everything up.</p>
      <label class="field">Which computer runs RaceManager's database?</label>
      <div class="row">
        <input id="admin-host" value="localhost" style="flex:1;min-width:160px">
        <button type="button" id="admin-discover-btn" class="secondary">Find it for me</button>
      </div>
      <p class="fieldhelp" id="admin-discover-msg"></p>
      <p class="fieldhelp">If BBS is installed on the same computer as RaceManager, leave this as <code>localhost</code>. Otherwise, enter that computer's name or address.</p>
      <label class="field">SQL Server administrator username</label>
      <input id="admin-user" autocomplete="off">
      <label class="field">SQL Server administrator password</label>
      <input id="admin-password" type="password" autocomplete="off">
      <p class="promise">Used once, right now, to set this up -- never saved, never logged, never shown again.</p>
      <details style="margin-top:8px"><summary class="muted">Advanced (only if you were told to change these)</summary>
        <label class="field">Database instance name</label>
        <input id="admin-instance" list="admin-instance-list">
        <datalist id="admin-instance-list"></datalist>
        <label class="field">TCP port (leave blank unless you were given one -- an instance name above takes priority over this)</label>
        <input id="admin-port" type="number">
        <label class="field">Database name</label>
        <input id="admin-database" value="RACE">
      </details>
      <div class="row" style="margin-top:12px">
        <button id="admin-setup-btn">Set it up</button>
        <span id="admin-setup-msg" class="muted"></span>
      </div>
    </div>

    <details id="verify-option">
      <summary>Already have a working login for BBS to use?</summary>
      <div class="option">
        <p class="muted">If <code>bbs_connector</code> already exists and you know its password, BBS can just verify it works and start using it. Nothing gets created or changed.</p>
        <label class="field">Which computer runs RaceManager's database?</label>
        <div class="row">
          <input id="verify-host" value="localhost" style="flex:1;min-width:160px">
          <button type="button" id="verify-discover-btn" class="secondary">Find it for me</button>
        </div>
        <p class="fieldhelp" id="verify-discover-msg"></p>
        <details style="margin-top:8px"><summary class="muted">Advanced</summary>
          <label class="field">Database instance name</label>
          <input id="verify-instance">
          <label class="field">TCP port (leave blank unless you were given one -- an instance name above takes priority over this)</label>
          <input id="verify-port" type="number">
          <label class="field">Database name</label>
          <input id="verify-database" value="RACE">
        </details>
        <label class="field">Password</label>
        <input id="verify-password" type="password" autocomplete="off">
        <div class="row" style="margin-top:12px">
          <button id="verify-btn">Verify and save</button>
          <span id="verify-msg" class="muted"></span>
        </div>
      </div>
    </details>

    <details id="dba-option">
      <summary>Prefer to have someone else run this?</summary>
      <div class="option">
        <p class="muted">Some tracks have a database administrator (DBA) or IT support who prefers to do this themselves. This generates the exact commands to hand them.</p>
        <p class="issue"><b>Whoever runs this needs to be a SQL Server administrator</b> (a "sysadmin", or a login with "ALTER ANY LOGIN" permission). Signing in as <code>bbs_connector</code> itself will not work -- it can only read race data, not create or change logins.</p>
        <label class="field">Database name</label>
        <input id="dba-database" value="RACE">
        <label class="row" style="margin-top:8px;font-weight:normal"><input type="checkbox" id="dba-reset"> This login already exists -- generate a password reset instead</label>
        <div class="row" style="margin-top:10px">
          <button id="dba-generate-btn">Generate the script</button>
          <button id="dba-copy-btn" class="secondary" style="display:none">Copy</button>
        </div>
        <pre id="dba-sql-text" style="display:none"></pre>
        <dl class="trouble" style="margin-top:14px">
          <dt>Msg 15151 ... Cannot alter the login ... you do not have permission</dt>
          <dd>The account that ran this isn't a SQL Server administrator. Reconnect as an administrator account (not <code>bbs_connector</code>) and try again.</dd>
          <dt>Msg 15025 ... The server principal already exists</dt>
          <dd>This login already exists. Check "This login already exists" above and generate a password reset instead, or use "Set it up automatically" -- it handles this by itself.</dd>
          <dt>Login failed for user '...'</dt>
          <dd>The username or password used to connect was wrong.</dd>
          <dt>A network-related or instance-specific error has occurred / Cannot connect to server</dt>
          <dd>Couldn't reach the SQL Server at all. Double-check the server name and instance, and that it accepts remote connections if it's on a different computer.</dd>
        </dl>
        <p class="muted" style="margin-top:10px">Once it's been run, use "Already have a working login for BBS to use?" above to finish.</p>
      </div>
    </details>

    <details style="margin-top:16px"><summary class="muted">Undo this later</summary>
      <p class="muted">Run this on the SQL Server to remove the account BBS created:</p>
      <pre id="sql-cleanup-text">Loading...</pre>
    </details>
  </div>
</div>

<div class="card" id="sqorz-card"><h2>3. Sqorz live timing<span id="sqorz-optional-label"> (optional)</span></h2>
  <p class="muted" id="sqorz-card-intro">Not required. <a href="/configuration">Configure it</a> if your track uses Sqorz.
  See <a href="/sqorz-status">Sqorz status</a> once it's set up.</p>
</div>

<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function showError(el, detail){
  if(el.nextElementSibling && el.nextElementSibling.classList.contains('detail')) el.nextElementSibling.remove();
  if(detail && typeof detail==='object'){
    el.innerHTML='<span style="color:#ff8b8b">'+esc(detail.message||'Failed.')+'</span>';
    if(detail.technical_detail){
      const d=document.createElement('div');d.className='detail';d.textContent=detail.technical_detail;el.after(d);
      setTimeout(()=>{if(d.isConnected)d.remove()},20000);
    }
  } else {
    el.innerHTML='<span style="color:#ff8b8b">'+esc(detail||'Failed.')+'</span>';
  }
}

async function loadStatus(){
  const r=await fetch('/api/setup/status',{cache:'no-store'});
  const d=await r.json();
  const badge=(ok)=>'<span class="badge '+(ok?'ok':'attention')+'">'+(ok?'OK':'NEEDS ATTENTION')+'</span>';
  document.querySelector('#overview-body').innerHTML=
    '<div>'+badge(d.odbc_driver.present)+' SQL Server driver</div>'
    +'<div style="margin-top:6px">'+badge(d.database.reachable)+' Database connection -- '+esc(d.database.detail)+'</div>'
    +'<div style="margin-top:6px">'+badge(d.racemanager.readable)+' RaceManager data -- '+esc(d.racemanager.detail)+'</div>'
    +'<div style="margin-top:6px">'+badge(d.sqorz.configured)+' Sqorz live timing (optional)</div>';

  const odbcBody=document.querySelector('#odbc-body');
  if(d.odbc_driver.present){
    odbcBody.innerHTML='<span class="badge ok">FOUND</span> '+esc(d.odbc_driver.preferred_driver);
    document.querySelector('#odbc-install-ui').style.display='none';
  } else {
    odbcBody.innerHTML='<span class="badge attention">NOT FOUND</span> Installed drivers: '+esc(d.odbc_driver.installed_drivers.join(', ')||'none');
    document.querySelector('#odbc-install-ui').style.display='block';
  }

  const alreadyDone=document.querySelector('#sql-already-done');
  const fullSection=document.querySelector('#sql-full-section');
  if(d.database.reachable && !fullSection.dataset.forcedOpen){
    document.querySelector('#sql-already-done-text').textContent=
      'Already set up. BBS is connected and reading RaceManager as "'+(d.database.sql_user||'')+'". There\'s nothing to do here.';
    alreadyDone.style.display='block';
    fullSection.style.display='none';
  } else if(!fullSection.dataset.forcedOpen){
    alreadyDone.style.display='none';
    fullSection.style.display='block';
  }
  return d;
}

document.querySelector('#sql-change-this').addEventListener('click', ()=>{
  document.querySelector('#sql-already-done').style.display='none';
  const fullSection=document.querySelector('#sql-full-section');
  fullSection.style.display='block';
  fullSection.dataset.forcedOpen='1';
});

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
  document.querySelector('#admin-instance-list').innerHTML=d.detected.map(i=>'<option value="'+esc(i)+'">').join('');
}

async function discoverSql(prefix){
  const host=document.querySelector('#'+prefix+'-host').value.trim();
  const msg=document.querySelector('#'+prefix+'-discover-msg');
  if(!host){msg.textContent='Enter a computer name or address first.';return}
  msg.textContent='Looking...';
  const r=await fetch('/api/setup/sql/discover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({host})});
  const d=await r.json();
  if(d.selected){
    document.querySelector('#'+prefix+'-instance').value=d.selected.instance||'';
    document.querySelector('#'+prefix+'-port').value=d.selected.port||'';
    const details=document.querySelector('#'+prefix+'-instance').closest('details');
    if(details) details.open=true;
  }
  msg.textContent=d.message||(d.found?'Found it.':"Couldn't find it -- enter it yourself if you know it.");
}
document.querySelector('#admin-discover-btn').addEventListener('click',()=>discoverSql('admin'));
document.querySelector('#verify-discover-btn').addEventListener('click',()=>discoverSql('verify'));

document.querySelector('#auto-setup-btn').addEventListener('click', async ()=>{
  const msg=document.querySelector('#auto-setup-msg');
  msg.textContent='Trying...'; msg.className='muted';
  const r=await fetch('/api/setup/sql/auto-setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
  const d=await r.json();
  if(r.ok && d.automatic){
    msg.textContent=(d.created?'Done. Created a new login and BBS is now reading RaceManager as it.':'Done. Reset the existing login and BBS is now reading RaceManager as it.');
    loadStatus();
    return;
  }
  msg.textContent="Couldn't set this up automatically -- that's normal, and doesn't mean anything is wrong. Enter administrator credentials below instead.";
  document.querySelector('#admin-setup-option').style.display='block';
});

document.querySelector('#admin-setup-btn').addEventListener('click', async ()=>{
  const msg=document.querySelector('#admin-setup-msg');
  msg.textContent='Working...'; msg.className='muted';
  const body={
    host: document.querySelector('#admin-host').value.trim(),
    instance: document.querySelector('#admin-instance').value.trim(),
    port: document.querySelector('#admin-port').value.trim(),
    database: document.querySelector('#admin-database').value.trim()||'RACE',
    admin_user: document.querySelector('#admin-user').value.trim(),
    admin_password: document.querySelector('#admin-password').value,
  };
  const r=await fetch('/api/setup/sql/admin-setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  document.querySelector('#admin-password').value='';
  if(!r.ok){showError(msg, d.detail); return}
  msg.textContent=(d.created?'Done. Created a new login and BBS is now reading RaceManager as it.':'Done. Reset the existing login and BBS is now reading RaceManager as it.');
  document.querySelector('#admin-user').value='';
  loadStatus();
});

document.querySelector('#verify-btn').addEventListener('click', async ()=>{
  const msg=document.querySelector('#verify-msg');
  msg.textContent='Verifying...';
  const body={
    host: document.querySelector('#verify-host').value.trim(),
    instance: document.querySelector('#verify-instance').value.trim(),
    port: document.querySelector('#verify-port').value.trim(),
    database: document.querySelector('#verify-database').value.trim()||'RACE',
    password: document.querySelector('#verify-password').value,
  };
  const r=await fetch('/api/setup/sql/verify-and-store',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  document.querySelector('#verify-password').value='';
  if(!r.ok){showError(msg, d.detail); return}
  msg.textContent='Verified: read a row from '+esc(d.proof.read_a_row_from)+'. BBS will use this from now on.';
  loadStatus();
});

document.querySelector('#dba-generate-btn').addEventListener('click', async ()=>{
  const resetPassword=document.querySelector('#dba-reset').checked;
  const body={database: document.querySelector('#dba-database').value.trim()||'RACE', reset_password: resetPassword};
  const r=await fetch('/api/setup/sql/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(!r.ok){return}
  const pre=document.querySelector('#dba-sql-text');
  pre.textContent=d.sql; pre.style.display='block';
  document.querySelector('#dba-copy-btn').style.display='inline-block';
  document.querySelector('#dba-copy-btn').dataset.sql=d.sql;
});
document.querySelector('#dba-copy-btn').addEventListener('click', async ()=>{
  try{await navigator.clipboard.writeText(document.querySelector('#dba-copy-btn').dataset.sql||'')}catch(e){}
});

async function loadCleanup(){
  const r=await fetch('/api/setup/sql/cleanup?database=RACE');
  const d=await r.json();
  document.querySelector('#sql-cleanup-text').textContent=d.sql;
}

const modeLabels={racemanager:'RaceManager',sqorz_only:'Sqorz-only',unavailable:'Unavailable'};
function renderModeBanner(decision){
  document.querySelector('#mode-value').textContent=modeLabels[decision.mode]||decision.mode;
  document.querySelector('#mode-reason').textContent=decision.reason;
}
async function loadMode(){
  try{
    const r=await fetch('/api/mode',{cache:'no-store'});
    if(!r.ok)throw new Error();
    renderModeBanner(await r.json());
  }catch(e){document.querySelector('#mode-reason').textContent='Mode unavailable.'}
}
document.querySelector('#mode-recheck').addEventListener('click', async ()=>{
  const button=document.querySelector('#mode-recheck');
  const detail=document.querySelector('#mode-recheck-detail');
  button.disabled=true;
  try{
    const r=await fetch('/api/mode/recheck',{method:'POST'});
    if(!r.ok)throw new Error('Request failed: '+r.status);
    const d=await r.json();
    renderModeBanner(d.after);
    detail.textContent='Before: '+(modeLabels[d.before.mode]||d.before.mode)+' ('+d.before.reason+') -- After: '+(modeLabels[d.after.mode]||d.after.mode)+' ('+d.after.reason+')';
  }catch(e){detail.textContent=String(e.message||e)}
  finally{button.disabled=false}
});

document.querySelector('#skip-to-sqorz').addEventListener('click', (event)=>{
  event.preventDefault();
  document.querySelector('#odbc-card').classList.add('skipped');
  document.querySelector('#sql-card').classList.add('skipped');
  document.querySelector('#sqorz-optional-label').remove();
  document.querySelector('#sqorz-card-intro').textContent='This is the only setup this track needs -- RaceManager\'s SQL Server driver and connection above can stay unconfigured. Configure Sqorz below, then use Re-check above to confirm BBS switched to Sqorz-only mode.';
  document.querySelector('#sqorz-card').scrollIntoView({behavior:'smooth'});
});

loadStatus();
loadInstances();
loadCleanup();
loadMode();
</script>
</body></html>'''
