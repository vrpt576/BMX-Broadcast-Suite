"""The Setup wizard's routes: prerequisite install, connecting BBS to
RaceManager (three ways), and the consolidated status. Loopback-only
enforcement itself is covered in test_network_security.py; this file
covers the route/business logic, with pyodbc/msiexec/the filesystem
faked out throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from connector.dependencies import get_sqorz_service
from connector.main import app
from connector.routes import setup as setup_route
from connector.routes.diagnostics import get_diagnostics_service
from connector.services import odbc_service
from connector.services import sql_setup_service as sql_setup
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


def test_status_reports_sql_user_for_the_already_configured_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "detect", lambda: odbc_service.OdbcDriverStatus(
        installed_drivers=["ODBC Driver 18 for SQL Server"],
        preferred_driver="ODBC Driver 18 for SQL Server",
        acceptable=True,
    ))
    app.dependency_overrides[get_diagnostics_service] = ok_diagnostics
    app.dependency_overrides[get_sqorz_service] = lambda: SqorzService(enabled=True)

    body = client.get("/api/setup/status").json()

    assert "sql_user" in body["database"]


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
# ODBC install
# ---------------------------------------------------------------------------


def test_license_serves_the_bundled_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    license_file = tmp_path / "ODBC-Driver-LICENSE.rtf"
    license_file.write_text("{\\rtf1 license}")
    monkeypatch.setattr(odbc_service, "bundled_license_path", lambda _root: license_file)

    response = client.get("/api/setup/odbc/license")

    assert response.status_code == 200


def test_license_404s_when_not_bundled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(odbc_service, "bundled_license_path", lambda _root: None)
    response = client.get("/api/setup/odbc/license")
    assert response.status_code == 404


def test_install_requires_agreement() -> None:
    response = client.post("/api/setup/odbc/install", json={"source": "bundled", "agree": False})
    assert response.status_code == 400


def test_install_validates_source() -> None:
    response = client.post("/api/setup/odbc/install", json={"source": "nonsense", "agree": True})
    assert response.status_code == 400


def test_install_bundled_409s_when_no_bundled_installer_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(odbc_service, "bundled_installer_path", lambda _root: None)
    response = client.post("/api/setup/odbc/install", json={"source": "bundled", "agree": True})
    assert response.status_code == 409


def test_install_bundled_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    msi = tmp_path / "driver.msi"
    msi.write_bytes(b"fake")
    monkeypatch.setattr(odbc_service, "bundled_installer_path", lambda _root: msi)
    monkeypatch.setattr(odbc_service, "install_from_msi", lambda _path: None)
    monkeypatch.setattr(odbc_service, "detect", lambda: odbc_service.OdbcDriverStatus(
        installed_drivers=["ODBC Driver 18 for SQL Server"],
        preferred_driver="ODBC Driver 18 for SQL Server",
        acceptable=True,
    ))

    response = client.post("/api/setup/odbc/install", json={"source": "bundled", "agree": True})

    assert response.status_code == 200
    assert response.json()["installed"] is True


def test_install_download_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    downloaded = tmp_path / "driver.msi"
    monkeypatch.setattr(odbc_service, "download_installer", lambda _dest: downloaded)
    monkeypatch.setattr(odbc_service, "install_from_msi", lambda _path: None)
    monkeypatch.setattr(odbc_service, "detect", lambda: odbc_service.OdbcDriverStatus(
        installed_drivers=["ODBC Driver 18 for SQL Server"],
        preferred_driver="ODBC Driver 18 for SQL Server",
        acceptable=True,
    ))

    response = client.post("/api/setup/odbc/install", json={"source": "download", "agree": True})

    assert response.status_code == 200


def test_install_surfaces_a_failure_plainly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    msi = tmp_path / "driver.msi"
    msi.write_bytes(b"fake")
    monkeypatch.setattr(odbc_service, "bundled_installer_path", lambda _root: msi)

    def boom(_path):
        raise odbc_service.OdbcInstallError("msiexec exited with code 1603")

    monkeypatch.setattr(odbc_service, "install_from_msi", boom)

    response = client.post("/api/setup/odbc/install", json={"source": "bundled", "agree": True})

    assert response.status_code == 500
    assert "1603" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/setup/sql/instances
# ---------------------------------------------------------------------------


def test_instances_falls_back_to_the_common_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_setup, "detect_local_sql_instances", lambda: [])
    response = client.get("/api/setup/sql/instances")
    assert response.json() == {"detected": [], "default": "USABMX"}


def test_instances_prefers_a_detected_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_setup, "detect_local_sql_instances", lambda: ["SQLEXPRESS", "USABMX"])
    response = client.get("/api/setup/sql/instances")
    assert response.json() == {"detected": ["SQLEXPRESS", "USABMX"], "default": "SQLEXPRESS"}


# ---------------------------------------------------------------------------
# POST /api/setup/sql/admin-setup -- the primary path
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


def test_admin_setup_requires_all_fields() -> None:
    response = client.post(
        "/api/setup/sql/admin-setup", json={"host": "localhost", "admin_user": "sa"}
    )
    assert response.status_code == 400


def test_admin_setup_creates_a_new_login_when_none_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    # admin connection: rights check -> 1, login_exists -> None (doesn't exist)
    admin_connection = FakeSqlConnection(script=[(1,), None])
    verify_connection = FakeSqlConnection(script=[(1, "a", "row")])
    connections = iter([admin_connection, verify_connection])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5: next(connections))
    saved = {}
    monkeypatch.setattr(
        setup_route.ConfigurationService, "save", lambda self, values: saved.update(values)
    )

    response = client.post(
        "/api/setup/sql/admin-setup",
        json={"host": "localhost", "instance": "USABMX", "admin_user": "sa", "admin_password": "AdminP@ss1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["created"] is True
    assert "CREATE LOGIN" in " ".join(admin_connection.executed)
    assert admin_connection.closed is True
    assert saved["sql_user"] == "bbs_connector"
    assert "AdminP@ss1" not in response.text  # the admin password never comes back


def test_admin_setup_resets_the_password_when_the_login_already_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_connection = FakeSqlConnection(script=[(1,), ("bbs_connector",)])
    verify_connection = FakeSqlConnection(script=[(1, "a", "row")])
    connections = iter([admin_connection, verify_connection])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5: next(connections))
    monkeypatch.setattr(setup_route.ConfigurationService, "save", lambda self, values: None)

    response = client.post(
        "/api/setup/sql/admin-setup",
        json={"host": "localhost", "admin_user": "sa", "admin_password": "AdminP@ss1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] is False
    assert "ALTER LOGIN" in " ".join(admin_connection.executed)
    assert "CREATE LOGIN" not in " ".join(admin_connection.executed)


def test_admin_setup_reports_a_bad_admin_login_plainly_without_a_raw_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(cs, timeout=5):
        raise sql_setup.SqlSetupError("Login failed for user 'sa'.")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/admin-setup",
        json={"host": "localhost", "admin_user": "sa", "admin_password": "wrong"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "sa" in detail["message"]
    assert "Login failed" in detail["technical_detail"]


def test_admin_setup_refuses_plainly_when_the_admin_account_cannot_manage_logins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_connection = FakeSqlConnection(script=[(0,)])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5: admin_connection)

    response = client.post(
        "/api/setup/sql/admin-setup",
        json={"host": "localhost", "admin_user": "read_only_reporting", "admin_password": "x"},
    )

    assert response.status_code == 409
    message = response.json()["detail"]["message"]
    assert "read_only_reporting" in message
    assert "ALTER ANY LOGIN" in message
    # Only the rights check itself ran -- nothing was attempted against
    # the login (no existence lookup, no CREATE/ALTER).
    assert len(admin_connection.executed) == 1
    assert admin_connection.closed is True


def test_admin_setup_never_echoes_the_admin_password_anywhere_in_the_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_connection = FakeSqlConnection(script=[(1,), None])
    verify_connection = FakeSqlConnection(script=[(1, "a", "row")])
    connections = iter([admin_connection, verify_connection])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5: next(connections))
    monkeypatch.setattr(setup_route.ConfigurationService, "save", lambda self, values: None)

    response = client.post(
        "/api/setup/sql/admin-setup",
        json={
            "host": "localhost",
            "admin_user": "sa",
            "admin_password": "a-very-recognizable-admin-secret",
        },
    )

    assert "a-very-recognizable-admin-secret" not in response.text


def test_admin_setup_rejects_a_malicious_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("must not attempt a connection for an invalid login_name")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/admin-setup",
        json={
            "host": "localhost",
            "admin_user": "sa",
            "admin_password": "x",
            "login_name": "bbs_connector]; DROP LOGIN [sa",
        },
    )

    assert response.status_code == 400


def test_admin_setup_honors_a_custom_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    admin_connection = FakeSqlConnection(script=[(1,), None])
    verify_connection = FakeSqlConnection(script=[(1, "a", "row")])
    connections = iter([admin_connection, verify_connection])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5: next(connections))
    saved = {}
    monkeypatch.setattr(
        setup_route.ConfigurationService, "save", lambda self, values: saved.update(values)
    )

    response = client.post(
        "/api/setup/sql/admin-setup",
        json={
            "host": "localhost",
            "admin_user": "sa",
            "admin_password": "x",
            "login_name": "bbs_connector_test",
        },
    )

    assert response.status_code == 200
    assert "bbs_connector_test" in " ".join(admin_connection.executed)
    assert saved["sql_user"] == "bbs_connector_test"


# ---------------------------------------------------------------------------
# POST /api/setup/sql/generate -- "hand it to a DBA": never attempts a
# connection, always available regardless of what any identity can or
# can't do.
# ---------------------------------------------------------------------------


def test_generate_never_attempts_a_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("sql/generate must never try to connect")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post("/api/setup/sql/generate", json={"database": "RACE"})

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "create_if_missing"
    assert "IF NOT EXISTS" in body["sql"]
    assert "CREATE LOGIN [bbs_connector]" in body["sql"]


def test_generate_offers_a_reset_password_variant_on_request() -> None:
    response = client.post("/api/setup/sql/generate", json={"database": "RACE", "reset_password": True})

    body = response.json()
    assert body["kind"] == "reset_password"
    assert body["sql"].strip().startswith("ALTER LOGIN [bbs_connector]")


def test_generate_honors_a_custom_login_name() -> None:
    response = client.post(
        "/api/setup/sql/generate", json={"database": "RACE", "login_name": "bbs_connector_test"}
    )
    assert "bbs_connector_test" in response.json()["sql"]


def test_generate_rejects_a_malicious_login_name() -> None:
    response = client.post(
        "/api/setup/sql/generate",
        json={"database": "RACE", "login_name": "bbs_connector]; DROP LOGIN [sa"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/setup/sql/verify-and-store -- "I already have the password"
# ---------------------------------------------------------------------------


def test_verify_and_store_saves_credentials_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(1, "row")])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5: connection)
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
    def boom(cs, timeout=5):
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
    assert "Login failed" in response.json()["detail"]["technical_detail"]


def test_verify_and_store_honors_a_custom_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(1, "row")])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5: connection)
    saved = {}
    monkeypatch.setattr(
        setup_route.ConfigurationService, "save", lambda self, values: saved.update(values)
    )

    response = client.post(
        "/api/setup/sql/verify-and-store",
        json={
            "host": "localhost",
            "instance": "USABMX",
            "database": "RACE",
            "password": "S3cret!Pass1234",
            "login_name": "bbs_connector_test",
        },
    )

    assert response.status_code == 200
    assert response.json()["proof"]["login"] == "bbs_connector_test"
    assert saved["sql_user"] == "bbs_connector_test"


def test_verify_and_store_rejects_a_malicious_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("must not attempt a connection for an invalid login_name")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/verify-and-store",
        json={
            "host": "localhost",
            "password": "x",
            "login_name": "bbs_connector]; DROP LOGIN [sa",
        },
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/setup/sql/cleanup
# ---------------------------------------------------------------------------


def test_cleanup_returns_read_only_sql() -> None:
    response = client.get("/api/setup/sql/cleanup", params={"database": "RACE"})
    assert response.status_code == 200
    sql = response.json()["sql"]
    assert "DROP LOGIN [bbs_connector]" in sql


def test_cleanup_honors_a_custom_login_name() -> None:
    response = client.get(
        "/api/setup/sql/cleanup", params={"database": "RACE", "login_name": "bbs_connector_test"}
    )
    assert "DROP LOGIN [bbs_connector_test]" in response.json()["sql"]


def test_cleanup_rejects_a_malicious_login_name() -> None:
    response = client.get(
        "/api/setup/sql/cleanup",
        params={"database": "RACE", "login_name": "bbs_connector]; DROP LOGIN [sa"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------


def test_the_page_serves_without_any_racemanager_dependency() -> None:
    response = client.get("/setup")
    assert response.status_code == 200
    assert "BBS Setup" in response.text


def test_the_page_never_echoes_a_password_placeholder_in_a_way_thats_pre_filled() -> None:
    response = client.get("/setup")
    for field_id in ("admin-password", "verify-password"):
        section = response.text.split(f'id="{field_id}"')[1].split(">")[0]
        assert "value=" not in section


def test_the_page_offers_all_three_paths() -> None:
    response = client.get("/setup")
    body = response.text
    assert "Set it up automatically" in body
    assert "Already have a working login for BBS to use?" in body
    assert "Prefer to have someone else run this?" in body


def test_the_page_never_generates_a_powershell_script() -> None:
    """CLAUDE.md forbids reintroducing an ExecutionPolicy-Bypass-shaped
    artifact after the Wacatac incident -- a downloadable .ps1 also just
    opens in Notepad rather than running for most operators. Confirm the
    page's own source contains no such thing."""
    response = client.get("/setup")
    assert ".ps1" not in response.text
    assert "ExecutionPolicy" not in response.text


def test_the_page_states_the_required_permission_for_the_dba_path() -> None:
    response = client.get("/setup")
    assert "SQL Server administrator" in response.text
    assert "ALTER ANY LOGIN" in response.text


def test_the_page_includes_troubleshooting_for_the_errors_that_actually_happen() -> None:
    response = client.get("/setup")
    body = response.text
    assert "Msg 15151" in body
    assert "Msg 15025" in body
    assert "Login failed for user" in body
    assert "network-related" in body or "Cannot connect to server" in body


def test_the_page_promises_the_admin_credentials_are_never_persisted() -> None:
    response = client.get("/setup")
    assert "never saved, never logged, never shown again" in response.text


def test_diagnostics_page_links_to_setup() -> None:
    response = client.get("/diagnostics")
    assert response.status_code == 200
    assert 'href="/setup"' in response.text
