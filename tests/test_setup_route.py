"""The Setup wizard's routes: prerequisite install, SQL account creation,
and the consolidated status. Loopback-only enforcement itself is covered
in test_network_security.py; this file covers the route/business logic,
with pyodbc/msiexec/the filesystem faked out throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from connector.dependencies import get_database, get_sql_wizard_plan_cache, get_sqorz_service
from connector.main import app
from connector.routes import setup as setup_route
from connector.routes.diagnostics import get_diagnostics_service
from connector.services import odbc_service
from connector.services import sql_setup_service as sql_setup
from connector.services.sql_setup_service import PlanCache
from connector.services.sqorz_service import SqorzService

client = TestClient(app)


class FakeDiagnostics:
    def __init__(self, checks: dict) -> None:
        self._checks = checks

    def run(self) -> dict:
        return {"checks": [{"key": k, **v} for k, v in self._checks.items()]}


def ok_diagnostics() -> FakeDiagnostics:
    return FakeDiagnostics(
        {
            "database": {"status": "ok", "detail": "Connected as bbs_connector."},
            "event": {"status": "ok", "detail": "Hoosier Day 3 -- 12 motos, 300 riders."},
        }
    )


def failing_diagnostics() -> FakeDiagnostics:
    return FakeDiagnostics(
        {
            "database": {"status": "error", "detail": "Login failed."},
            "event": {"status": "warning", "detail": "Skipped because the database login failed."},
        }
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/setup/status
# ---------------------------------------------------------------------------


def test_status_reports_all_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "detect", lambda: odbc_service.OdbcDriverStatus(
        installed_drivers=["ODBC Driver 18 for SQL Server"],
        preferred_driver="ODBC Driver 18 for SQL Server",
        acceptable=True,
    ))
    app.dependency_overrides[get_diagnostics_service] = ok_diagnostics
    app.dependency_overrides[get_sqorz_service] = lambda: SqorzService(enabled=True)

    response = client.get("/api/setup/status")

    assert response.status_code == 200
    body = response.json()
    assert body["odbc_driver"]["present"] is True
    assert body["odbc_driver"]["fix_it"] is None
    assert body["database"]["reachable"] is True
    assert body["racemanager"]["readable"] is True
    assert body["sqorz"]["configured"] is True


def test_status_offers_fix_it_links_when_something_is_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "detect", lambda: odbc_service.OdbcDriverStatus(
        installed_drivers=[], preferred_driver=None, acceptable=False
    ))
    app.dependency_overrides[get_diagnostics_service] = failing_diagnostics
    app.dependency_overrides[get_sqorz_service] = lambda: SqorzService(enabled=False)

    body = client.get("/api/setup/status").json()

    assert body["odbc_driver"]["present"] is False
    assert body["odbc_driver"]["fix_it"] == "/setup#odbc"
    assert body["database"]["reachable"] is False
    assert body["database"]["fix_it"] == "/setup#sql"
    assert body["sqorz"]["configured"] is False
    assert body["sqorz"]["fix_it"] == "/configuration"


# ---------------------------------------------------------------------------
# ODBC license + install
# ---------------------------------------------------------------------------


def test_license_404_when_no_bundled_copy_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "bundled_license_path", lambda root: None)
    response = client.get("/api/setup/odbc/license")
    assert response.status_code == 404


def test_license_serves_the_real_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    license_file = tmp_path / "ODBC-Driver-LICENSE.rtf"
    license_file.write_text("{\\rtf1 license text}")
    monkeypatch.setattr(odbc_service, "bundled_license_path", lambda root: license_file)

    response = client.get("/api/setup/odbc/license")

    assert response.status_code == 200
    assert b"license text" in response.content


def test_install_requires_explicit_agreement() -> None:
    response = client.post("/api/setup/odbc/install", json={"source": "bundled", "agree": False})
    assert response.status_code == 400
    assert "agree" in response.json()["detail"].lower()


def test_install_rejects_an_unknown_source() -> None:
    response = client.post("/api/setup/odbc/install", json={"source": "usb-stick", "agree": True})
    assert response.status_code == 400


def test_install_bundled_success_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    msi = tmp_path / "driver.msi"
    msi.write_bytes(b"fake")
    monkeypatch.setattr(odbc_service, "bundled_installer_path", lambda root: msi)
    installed = {}
    monkeypatch.setattr(odbc_service, "install_from_msi", lambda path: installed.setdefault("path", path))
    monkeypatch.setattr(odbc_service, "detect", lambda: odbc_service.OdbcDriverStatus(
        installed_drivers=["ODBC Driver 18 for SQL Server"],
        preferred_driver="ODBC Driver 18 for SQL Server",
        acceptable=True,
    ))

    response = client.post("/api/setup/odbc/install", json={"source": "bundled", "agree": True})

    assert response.status_code == 200
    assert response.json()["installed"] is True
    assert installed["path"] == msi


def test_install_bundled_missing_reports_409(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "bundled_installer_path", lambda root: None)
    response = client.post("/api/setup/odbc/install", json={"source": "bundled", "agree": True})
    assert response.status_code == 409


def test_install_download_path_invokes_download_then_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = []
    monkeypatch.setattr(
        odbc_service, "download_installer", lambda dest, **k: (calls.append(("download", dest)), dest)[1]
    )
    monkeypatch.setattr(odbc_service, "install_from_msi", lambda path: calls.append(("install", path)))
    monkeypatch.setattr(odbc_service, "detect", lambda: odbc_service.OdbcDriverStatus(
        installed_drivers=["ODBC Driver 18 for SQL Server"],
        preferred_driver="ODBC Driver 18 for SQL Server",
        acceptable=True,
    ))

    response = client.post("/api/setup/odbc/install", json={"source": "download", "agree": True})

    assert response.status_code == 200
    assert [c[0] for c in calls] == ["download", "install"]


def test_install_failure_surfaces_the_real_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    msi = tmp_path / "driver.msi"
    msi.write_bytes(b"fake")
    monkeypatch.setattr(odbc_service, "bundled_installer_path", lambda root: msi)

    def boom(path):
        raise odbc_service.OdbcInstallError("msiexec exited with code 1603")

    monkeypatch.setattr(odbc_service, "install_from_msi", boom)

    response = client.post("/api/setup/odbc/install", json={"source": "bundled", "agree": True})

    assert response.status_code == 500
    assert "1603" in response.json()["detail"]


# ---------------------------------------------------------------------------
# SQL instances
# ---------------------------------------------------------------------------


def test_sql_instances_uses_the_common_default_when_none_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_setup, "detect_local_sql_instances", lambda: [])
    response = client.get("/api/setup/sql/instances")
    assert response.json() == {"detected": [], "default": "USABMX"}


def test_sql_instances_prefers_a_detected_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_setup, "detect_local_sql_instances", lambda: ["SQLEXPRESS", "USABMX"])
    response = client.get("/api/setup/sql/instances")
    assert response.json() == {"detected": ["SQLEXPRESS", "USABMX"], "default": "SQLEXPRESS"}


# ---------------------------------------------------------------------------
# SQL preflight / plan / apply / verify-and-store / cleanup
# ---------------------------------------------------------------------------


class FakeSqlConnection:
    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.closed = False
        self.executed: list[str] = []

    def cursor(self):
        return self

    def execute(self, sql, params=()):
        self.executed.append(sql)

    def fetchone(self):
        return self._script.pop(0) if self._script else None

    def close(self):
        self.closed = True

    def commit(self):
        pass


def test_preflight_reports_a_connection_failure_plainly(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(connection_string, timeout=5.0):
        raise sql_setup.SqlSetupError("Login failed for user 'NT AUTHORITY\\SYSTEM'.")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/preflight",
        json={"host": "localhost", "instance": "USABMX", "database": "RACE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["connected_with_windows_auth"] is False
    assert "Login failed" in body["connection_error"]
    assert body["can_run_automatically"] is False


def test_preflight_reports_mixed_mode_blocking_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(1, "SQL Server"), None])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)

    response = client.post(
        "/api/setup/sql/preflight",
        json={"host": "localhost", "instance": "USABMX", "database": "RACE"},
    )

    body = response.json()
    assert body["connected_with_windows_auth"] is True
    assert body["integrated_security_only"] is True
    assert len(body["blocking_issues"]) == 1
    assert connection.closed is True  # preflight always releases its connection


def test_preflight_requires_a_host() -> None:
    response = client.post("/api/setup/sql/preflight", json={"instance": "USABMX"})
    assert response.status_code == 400


def test_plan_generates_a_create_plan_when_no_existing_login(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(0, "SQL Server"), None])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)

    response = client.post(
        "/api/setup/sql/plan", json={"host": "localhost", "instance": "USABMX", "database": "RACE"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "create"
    assert "CREATE LOGIN [bbs_connector]" in body["sql"]
    assert body["plan_id"]


def test_plan_generates_a_reset_plan_when_login_already_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(0, "SQL Server"), ("bbs_connector",)])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)

    response = client.post(
        "/api/setup/sql/plan", json={"host": "localhost", "instance": "USABMX", "database": "RACE"}
    )

    assert response.json()["kind"] == "reset_password"


def test_plan_refuses_when_it_cannot_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(cs, timeout=5.0):
        raise sql_setup.SqlSetupError("access denied")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/plan", json={"host": "localhost", "instance": "USABMX", "database": "RACE"}
    )

    assert response.status_code == 409


def test_plan_refuses_when_mixed_mode_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(1, "SQL Server"), None])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)

    response = client.post(
        "/api/setup/sql/plan", json={"host": "localhost", "instance": "USABMX", "database": "RACE"}
    )

    assert response.status_code == 409
    assert connection.closed is True


def test_apply_runs_the_cached_plan_then_verifies_and_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = PlanCache()
    plan = sql_setup.build_create_plan(database="RACE")
    plan_id = cache.store(plan, host="localhost", instance="USABMX", database="RACE")
    app.dependency_overrides[get_sql_wizard_plan_cache] = lambda: cache
    app.dependency_overrides[get_database] = lambda: object()

    apply_connection = FakeSqlConnection(script=[])
    verify_connection = FakeSqlConnection(script=[(1, "a", "row")])
    connections = iter([apply_connection, verify_connection])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: next(connections))

    saved = {}
    monkeypatch.setattr(
        setup_route.ConfigurationService, "save", lambda self, values: saved.update(values)
    )

    response = client.post(
        "/api/setup/sql/apply",
        json={"plan_id": plan_id, "host": "localhost", "instance": "USABMX", "database": "RACE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["proof"]["read_a_row_from"] == "Evt.Races"
    assert "CREATE LOGIN" in " ".join(apply_connection.executed)
    assert saved["sql_user"] == "bbs_connector"
    assert saved["sql_password"] == plan.password
    # The password must never come back in the response.
    assert plan.password not in response.text


def test_apply_rejects_an_unknown_or_reused_plan_id() -> None:
    cache = PlanCache()
    app.dependency_overrides[get_sql_wizard_plan_cache] = lambda: cache
    app.dependency_overrides[get_database] = lambda: object()

    response = client.post(
        "/api/setup/sql/apply",
        json={"plan_id": "not-a-real-plan", "host": "localhost", "instance": "USABMX", "database": "RACE"},
    )

    assert response.status_code == 400


def test_apply_falls_back_to_manual_instructions_when_it_cannot_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = PlanCache()
    plan = sql_setup.build_create_plan(database="RACE")
    plan_id = cache.store(plan, host="localhost", instance="USABMX", database="RACE")
    app.dependency_overrides[get_sql_wizard_plan_cache] = lambda: cache
    app.dependency_overrides[get_database] = lambda: object()

    def boom(cs, timeout=5.0):
        raise sql_setup.SqlSetupError("access denied")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/apply",
        json={"plan_id": plan_id, "host": "localhost", "instance": "USABMX", "database": "RACE"},
    )

    assert response.status_code == 409
    assert "yourself" in response.json()["detail"].lower()


def test_verify_and_store_saves_credentials_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(1, "row")])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)
    saved = {}
    monkeypatch.setattr(
        setup_route.ConfigurationService, "save", lambda self, values: saved.update(values)
    )

    response = client.post(
        "/api/setup/sql/verify-and-store",
        json={"host": "localhost", "instance": "USABMX", "database": "RACE", "password": "S3cret!Pass1234"},
    )

    assert response.status_code == 200
    assert saved["sql_password"] == "S3cret!Pass1234"
    assert "S3cret!Pass1234" not in response.text


def test_verify_and_store_requires_a_password() -> None:
    response = client.post(
        "/api/setup/sql/verify-and-store", json={"host": "localhost", "instance": "USABMX"}
    )
    assert response.status_code == 400


def test_verify_and_store_reports_a_bad_password_without_saving_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(cs, timeout=5.0):
        raise sql_setup.SqlSetupError("Login failed for user 'bbs_connector'.")

    monkeypatch.setattr(sql_setup, "connect", boom)
    saved = {}
    monkeypatch.setattr(
        setup_route.ConfigurationService, "save", lambda self, values: saved.update(values)
    )

    response = client.post(
        "/api/setup/sql/verify-and-store",
        json={"host": "localhost", "instance": "USABMX", "database": "RACE", "password": "wrong"},
    )

    assert response.status_code == 409
    assert saved == {}


def test_cleanup_returns_read_only_sql() -> None:
    response = client.get("/api/setup/sql/cleanup", params={"database": "RACE"})
    assert response.status_code == 200
    sql = response.json()["sql"]
    assert "DROP LOGIN [bbs_connector]" in sql


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------


def test_the_page_serves_without_any_racemanager_dependency() -> None:
    response = client.get("/setup")
    assert response.status_code == 200
    assert "BBS Setup" in response.text


def test_the_page_never_echoes_a_password_placeholder_in_a_way_thats_pre_filled() -> None:
    response = client.get("/setup")
    assert 'value="' not in response.text.split('id="sql-manual-password"')[1].split(">")[0]


def test_diagnostics_page_links_to_setup() -> None:
    response = client.get("/diagnostics")
    assert response.status_code == 200
    assert 'href="/setup"' in response.text
