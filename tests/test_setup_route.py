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
    connection = FakeSqlConnection(script=[(1, "SQL Server", 0), None])
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


def test_preflight_reports_when_the_service_account_is_sysadmin(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(0, "SQL Server", 1), None])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)

    response = client.post(
        "/api/setup/sql/preflight",
        json={"host": "localhost", "instance": "USABMX", "database": "RACE"},
    )

    assert response.json()["service_account_is_sysadmin"] is True


def test_preflight_requires_a_host() -> None:
    response = client.post("/api/setup/sql/preflight", json={"instance": "USABMX"})
    assert response.status_code == 400


def test_preflight_passes_an_integer_timeout_through_to_pyodbc(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end regression test for a real bug: sql_setup.connect() and
    the route's own _timeout() helper both used to produce a float, and
    pyodbc.connect()'s timeout kwarg maps to a C long -- a float there
    raises TypeError from inside pyodbc.connect() itself, turning "check
    connection automatically" (Path A's whole automatic flow) into a raw
    500 instead of a reported connection failure. Exercises the real
    sql_setup.connect() and _timeout(), not a mocked-out connect()."""

    class FakeError(Exception):
        pass

    class FakePyodbc:
        Error = FakeError

        @staticmethod
        def connect(connection_string, *, timeout, autocommit):
            if not isinstance(timeout, int) or isinstance(timeout, bool):
                raise TypeError("'float' object cannot be interpreted as an integer")
            raise FakeError("Login failed for user 'NT AUTHORITY\\SYSTEM'.")

    monkeypatch.setattr(sql_setup, "pyodbc", FakePyodbc())

    response = client.post(
        "/api/setup/sql/preflight",
        json={"host": "localhost", "instance": "USABMX", "database": "RACE"},
    )

    assert response.status_code == 200
    assert "Login failed" in response.json()["connection_error"]


def test_plan_generates_a_create_plan_when_no_existing_login(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(0, "SQL Server", 0), None])
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
    connection = FakeSqlConnection(script=[(0, "SQL Server", 0), ("bbs_connector",)])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)

    response = client.post(
        "/api/setup/sql/plan", json={"host": "localhost", "instance": "USABMX", "database": "RACE"}
    )

    assert response.json()["kind"] == "reset_password"


def test_plan_honors_a_custom_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(0, "SQL Server", 0), None])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)

    response = client.post(
        "/api/setup/sql/plan",
        json={
            "host": "localhost",
            "instance": "USABMX",
            "database": "RACE",
            "login_name": "bbs_connector_test",
        },
    )

    assert "bbs_connector_test" in response.json()["sql"]


def test_plan_refuses_when_it_cannot_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(cs, timeout=5.0):
        raise sql_setup.SqlSetupError("access denied")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/plan", json={"host": "localhost", "instance": "USABMX", "database": "RACE"}
    )

    assert response.status_code == 409


def test_plan_refuses_when_mixed_mode_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(1, "SQL Server", 0), None])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)

    response = client.post(
        "/api/setup/sql/plan", json={"host": "localhost", "instance": "USABMX", "database": "RACE"}
    )

    assert response.status_code == 409
    assert connection.closed is True


# ---------------------------------------------------------------------------
# POST /api/setup/sql/generate -- the separate-computer path: never attempts
# a connection, always available regardless of what BBS's service identity
# can or can't do.
# ---------------------------------------------------------------------------


def test_generate_never_attempts_a_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("sql/generate must never try to connect")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/generate", json={"host": "some-other-machine", "database": "RACE"}
    )

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


# ---------------------------------------------------------------------------
# login_name validation -- a malicious login_name must be rejected with a
# clean 400 before it ever reaches SQL text or a connection string, on
# every endpoint that accepts it. See sql_setup_service.validate_login_name.
# ---------------------------------------------------------------------------


MALICIOUS_LOGIN_NAME = "bbs_connector]; DROP LOGIN [sa"


def test_preflight_rejects_a_malicious_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("must not attempt a connection for an invalid login_name")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/preflight",
        json={"host": "localhost", "instance": "USABMX", "login_name": MALICIOUS_LOGIN_NAME},
    )

    assert response.status_code == 400


def test_plan_rejects_a_malicious_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("must not attempt a connection for an invalid login_name")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/plan",
        json={"host": "localhost", "instance": "USABMX", "login_name": MALICIOUS_LOGIN_NAME},
    )

    assert response.status_code == 400


def test_generate_rejects_a_malicious_login_name() -> None:
    response = client.post(
        "/api/setup/sql/generate", json={"database": "RACE", "login_name": MALICIOUS_LOGIN_NAME}
    )
    assert response.status_code == 400


def test_verify_and_store_rejects_a_malicious_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("must not attempt a connection for an invalid login_name")

    monkeypatch.setattr(sql_setup, "connect", boom)

    response = client.post(
        "/api/setup/sql/verify-and-store",
        json={
            "host": "localhost",
            "instance": "USABMX",
            "password": "S3cret!Pass1234",
            "login_name": MALICIOUS_LOGIN_NAME,
        },
    )

    assert response.status_code == 400


def test_cleanup_rejects_a_malicious_login_name() -> None:
    response = client.get(
        "/api/setup/sql/cleanup", params={"database": "RACE", "login_name": MALICIOUS_LOGIN_NAME}
    )
    assert response.status_code == 400


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


def test_apply_verifies_and_saves_under_the_plans_custom_login_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirms sql_apply reads login_name back off the cached plan rather
    than assuming bbs_connector -- otherwise a throwaway test login (see
    docs/setup-wizard.md's testing aids) would be created successfully but
    then verified/saved under the wrong name."""
    cache = PlanCache()
    plan = sql_setup.build_create_plan(database="RACE", login_name="bbs_connector_test")
    plan_id = cache.store(
        plan, host="localhost", instance="USABMX", database="RACE", login_name="bbs_connector_test"
    )
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
    assert response.json()["proof"]["login"] == "bbs_connector_test"
    assert saved["sql_user"] == "bbs_connector_test"


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


def test_verify_and_store_honors_a_custom_login_name(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSqlConnection(script=[(1, "row")])
    monkeypatch.setattr(sql_setup, "connect", lambda cs, timeout=5.0: connection)
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


def test_the_page_asks_about_topology_before_attempting_anything() -> None:
    """The core of requirement 1: the operator is asked up front whether
    BBS shares a computer with RaceManager, and the "different computer"
    answer is framed as a normal setup, not a failure state to recover
    from."""
    response = client.get("/setup")
    assert "same computer as RaceManager" in response.text
    assert "a different computer" in response.text.lower()
    assert "normal, expected setup" in response.text


def test_the_page_reassures_rather_than_alarms_when_the_automatic_attempt_fails() -> None:
    """When the same-computer automatic connection attempt fails, the copy
    must explain that's expected and point at the manual route -- not read
    as "you broke something.\""""
    response = client.get("/setup")
    assert "can happen even on the same computer" in response.text
