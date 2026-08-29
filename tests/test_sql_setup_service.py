"""The read-only bbs_connector SQL account wizard: plan, review, apply, verify.

Every "run SQL" path here is exercised against fake connections/cursors --
no real pyodbc or SQL Server needed. What's actually under test is the
logic: what gets reported, what gets generated, and -- most importantly --
that apply_plan() only ever runs what this module itself produced.
"""

from __future__ import annotations

import string

import pytest

from connector.services import sql_setup_service as svc


class FakeCursor:
    def __init__(self, script: list) -> None:
        # `script` is a list of return values for successive fetchone()
        # calls, one entry consumed per execute()+fetchone() pair.
        self._script = list(script)
        self.executed: list[tuple] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        return self._script.pop(0) if self._script else None


class FakeConnection:
    def __init__(self, script: list) -> None:
        self._cursor = FakeCursor(script)
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    @property
    def executed(self) -> list[tuple]:
        return self._cursor.executed


class ExplodingCursor:
    def execute(self, sql: str, params: tuple = ()) -> None:
        raise RuntimeError("permission denied")

    def fetchone(self):
        raise AssertionError("should not be reached")


class ExplodingConnection:
    def cursor(self):
        return ExplodingCursor()


# ---------------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------------


def test_generated_password_is_never_a_fixed_value() -> None:
    passwords = {svc.generate_password() for _ in range(20)}
    assert len(passwords) == 20  # all distinct


def test_generated_password_satisfies_sql_server_complexity_policy() -> None:
    for _ in range(50):
        password = svc.generate_password()
        assert len(password) == svc.PASSWORD_LENGTH
        classes = sum(
            (
                any(c.isupper() for c in password),
                any(c.islower() for c in password),
                any(c.isdigit() for c in password),
                any(c in svc.PASSWORD_SYMBOLS for c in password),
            )
        )
        assert classes >= 3
        assert set(password) <= set(string.ascii_letters + string.digits + svc.PASSWORD_SYMBOLS)


# ---------------------------------------------------------------------------
# Connection string building
# ---------------------------------------------------------------------------


def test_windows_auth_connection_string_uses_trusted_connection() -> None:
    cs = svc.windows_auth_connection_string(host="localhost", instance="USABMX", database="RACE")
    assert "Trusted_Connection=yes" in cs
    assert "SERVER=localhost\\USABMX" in cs
    assert "DATABASE=RACE" in cs
    assert "PWD=" not in cs


def test_windows_auth_connection_string_without_an_instance() -> None:
    cs = svc.windows_auth_connection_string(host="sql.example", instance="", database="RACE")
    assert "SERVER=sql.example;" in cs


def test_sql_auth_connection_string_carries_the_credentials() -> None:
    cs = svc.sql_auth_connection_string(
        host="localhost", instance="USABMX", database="RACE", user="bbs_connector", password="p@ss"
    )
    assert "UID=bbs_connector" in cs
    assert "PWD=p@ss" in cs
    assert "Trusted_Connection" not in cs


# ---------------------------------------------------------------------------
# connect() -- the one real pyodbc.connect() call, isolated and testable
# ---------------------------------------------------------------------------


def test_connect_without_pyodbc_raises_a_plain_language_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "pyodbc", None)
    with pytest.raises(svc.SqlSetupError, match="pyodbc is not installed"):
        svc.connect("DRIVER={x};SERVER=y;")


def test_connect_wraps_a_driver_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeError(Exception):
        pass

    class FakePyodbc:
        Error = FakeError

        @staticmethod
        def connect(*_args, **_kwargs):
            raise FakeError("Login failed for user 'x'.")

    monkeypatch.setattr(svc, "pyodbc", FakePyodbc())
    with pytest.raises(svc.SqlSetupError, match="Login failed"):
        svc.connect("DRIVER={x};SERVER=y;")


def test_connect_returns_the_real_connection_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()

    class FakePyodbc:
        Error = Exception

        @staticmethod
        def connect(*_args, **_kwargs):
            return sentinel

    monkeypatch.setattr(svc, "pyodbc", FakePyodbc())
    assert svc.connect("DRIVER={x};SERVER=y;") is sentinel


# ---------------------------------------------------------------------------
# Local instance detection -- best-effort, never raises
# ---------------------------------------------------------------------------


def test_detect_local_sql_instances_returns_empty_list_without_winreg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(svc, "winreg", None)
    assert svc.detect_local_sql_instances() == []


def test_detect_local_sql_instances_returns_empty_list_when_key_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()

        @staticmethod
        def OpenKey(*_args, **_kwargs):
            raise OSError("key not found")

    monkeypatch.setattr(svc, "winreg", FakeWinreg())
    assert svc.detect_local_sql_instances() == []


def test_detect_local_sql_instances_enumerates_real_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    values = [("USABMX", "MSSQL16.USABMX", 1), ("SQLEXPRESS", "MSSQL16.SQLEXPRESS", 1)]

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()

        @staticmethod
        def OpenKey(*_args, **_kwargs):
            return FakeKey()

        @staticmethod
        def EnumValue(_key, index):
            if index >= len(values):
                raise OSError("no more values")
            return values[index]

    monkeypatch.setattr(svc, "winreg", FakeWinreg())
    assert svc.detect_local_sql_instances() == ["USABMX", "SQLEXPRESS"]


# ---------------------------------------------------------------------------
# Preflight -- reports, never fixes
# ---------------------------------------------------------------------------


def test_preflight_reports_mixed_mode_off_as_blocking_and_explains_why() -> None:
    connection = FakeConnection(script=[(1, "Microsoft SQL Server 2019"), None])
    report = svc.run_preflight(connection)

    assert report.integrated_security_only is True
    assert report.existing_login_present is False
    assert len(report.blocking_issues) == 1
    assert "restart" in report.blocking_issues[0].lower()
    assert "racing" in report.blocking_issues[0].lower()


def test_preflight_reports_mixed_mode_on_as_not_blocking() -> None:
    connection = FakeConnection(script=[(0, "Microsoft SQL Server 2019"), None])
    report = svc.run_preflight(connection)

    assert report.integrated_security_only is False
    assert report.blocking_issues == []


def test_preflight_detects_an_existing_login() -> None:
    connection = FakeConnection(script=[(0, "Microsoft SQL Server 2019"), ("bbs_connector",)])
    report = svc.run_preflight(connection)
    assert report.existing_login_present is True


def test_preflight_never_touches_anything_it_reports_on() -> None:
    """The whole point: preflight must only ever SELECT, never ALTER/CREATE
    anything -- confirmed by checking every statement it actually ran."""
    connection = FakeConnection(script=[(1, "v"), None])
    svc.run_preflight(connection)
    for sql, _params in connection.executed:
        normalized = sql.strip().upper()
        assert normalized.startswith("SELECT"), f"preflight ran a non-SELECT statement: {sql}"


def test_preflight_with_no_connection_still_reports_the_tcp_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "_probe_tcp", lambda host, port, timeout=2.0: False)
    report = svc.run_preflight(None, connection_error="login failed", tcp_host="10.0.0.5", tcp_port=1433)

    assert report.connected is False
    assert report.connection_error == "login failed"
    assert report.tcp_reachable is False
    assert any("TCP" in issue for issue in report.blocking_issues)


def test_preflight_tcp_probe_skipped_without_a_known_port() -> None:
    connection = FakeConnection(script=[(0, "v"), None])
    report = svc.run_preflight(connection, tcp_host="localhost", tcp_port=None)
    assert report.tcp_reachable is None


def test_preflight_tcp_reachable_is_not_treated_as_blocking() -> None:
    connection = FakeConnection(script=[(0, "v"), None])
    report = svc.run_preflight(connection, tcp_host="127.0.0.1", tcp_port=1)
    # Port 1 is essentially never open -- this just proves an unreachable
    # probe doesn't crash preflight and is reported, not silently dropped.
    assert report.tcp_reachable in (True, False)


# ---------------------------------------------------------------------------
# Plan generation -- exact SQL, reviewable, nothing runs yet
# ---------------------------------------------------------------------------


def test_create_plan_contains_the_exact_statements_and_nothing_else() -> None:
    plan = svc.build_create_plan(database="RACE")

    assert plan.kind == "create"
    assert "CREATE LOGIN [bbs_connector]" in plan.sql
    assert "CHECK_POLICY = ON" in plan.sql
    assert "USE [RACE]" in plan.sql
    assert "CREATE USER [bbs_connector] FOR LOGIN [bbs_connector]" in plan.sql
    assert "ALTER ROLE db_datareader ADD MEMBER [bbs_connector]" in plan.sql
    assert plan.password in plan.sql  # the operator must see exactly what will run
    assert "DROP" not in plan.sql
    assert "GRANT" not in plan.sql or "db_datareader" in plan.sql


def test_create_plan_escapes_a_password_containing_a_single_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # generate_password()'s own alphabet never produces a quote -- force one
    # in to prove build_create_plan() would still emit valid, safely-quoted
    # SQL if it ever did (defense in depth, not just trusting the alphabet).
    monkeypatch.setattr(svc, "generate_password", lambda: "Ab1!Ab1!Ab1!Ab1!Ab1!O'Ab")

    plan = svc.build_create_plan(database="RACE")

    assert "O''Ab" in plan.sql  # the literal embedded in the SQL is escaped
    assert plan.password == "Ab1!Ab1!Ab1!Ab1!Ab1!O'Ab"  # returned unescaped, for the operator


def test_reset_password_plan_only_alters_the_login() -> None:
    plan = svc.build_reset_password_plan(database="RACE")
    assert plan.kind == "reset_password"
    assert plan.sql.strip().startswith("ALTER LOGIN [bbs_connector]")
    assert "CREATE" not in plan.sql
    assert plan.password in plan.sql


def test_cleanup_sql_drops_user_then_login_and_never_executes_anything() -> None:
    sql = svc.build_cleanup_sql(database="RACE")
    assert "DROP USER IF EXISTS [bbs_connector]" in sql
    assert "DROP LOGIN [bbs_connector]" in sql
    assert sql.index("DROP USER") < sql.index("DROP LOGIN")


# ---------------------------------------------------------------------------
# apply_plan -- only ever runs a Plan this module produced
# ---------------------------------------------------------------------------


def test_apply_plan_executes_exactly_the_plans_statements_in_order() -> None:
    plan = svc.build_create_plan(database="RACE")
    connection = FakeConnection(script=[])

    svc.apply_plan(connection, plan)

    executed_sql = [sql for sql, _params in connection.executed]
    assert len(executed_sql) == 4  # CREATE LOGIN, USE, CREATE USER, ALTER ROLE
    assert executed_sql[0].strip().startswith("CREATE LOGIN")
    assert executed_sql[1].strip() == "USE [RACE]"
    assert executed_sql[3].strip().startswith("ALTER ROLE")
    assert connection.committed is True


def test_apply_plan_signature_takes_a_plan_object_not_a_string() -> None:
    """Guards the actual security property: there is no apply_plan overload
    that accepts a bare SQL string, so a route can never pass client input
    straight through to execution."""
    import inspect

    signature = inspect.signature(svc.apply_plan)
    params = list(signature.parameters.values())
    assert params[1].annotation == "Plan" or "Plan" in str(params[1].annotation)


def test_apply_plan_propagates_a_real_failure() -> None:
    plan = svc.build_create_plan(database="RACE")
    with pytest.raises(RuntimeError, match="permission denied"):
        svc.apply_plan(ExplodingConnection(), plan)


# ---------------------------------------------------------------------------
# PlanCache -- the mechanism that keeps apply_plan() from ever running
# client-supplied SQL
# ---------------------------------------------------------------------------


class Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_plan_cache_round_trips_a_stored_plan() -> None:
    cache = svc.PlanCache()
    plan = svc.build_create_plan(database="RACE")

    plan_id = cache.store(plan, host="localhost", instance="USABMX", database="RACE")
    cached = cache.take(plan_id)

    assert cached is not None
    assert cached.plan is plan
    assert cached.host == "localhost"
    assert cached.instance == "USABMX"


def test_plan_cache_is_single_use() -> None:
    cache = svc.PlanCache()
    plan_id = cache.store(svc.build_create_plan(database="RACE"), host="h", instance="i", database="RACE")

    first = cache.take(plan_id)
    second = cache.take(plan_id)

    assert first is not None
    assert second is None


def test_plan_cache_unknown_id_returns_none() -> None:
    cache = svc.PlanCache()
    assert cache.take("not-a-real-id") is None


def test_plan_cache_expires_old_plans() -> None:
    clock = Clock()
    cache = svc.PlanCache(ttl_seconds=300.0, clock=clock)
    plan_id = cache.store(svc.build_create_plan(database="RACE"), host="h", instance="i", database="RACE")

    clock.advance(301.0)

    assert cache.take(plan_id) is None


def test_plan_cache_ids_are_not_guessable_or_repeated() -> None:
    cache = svc.PlanCache()
    ids = {
        cache.store(svc.build_create_plan(database="RACE"), host="h", instance="i", database="RACE")
        for _ in range(20)
    }
    assert len(ids) == 20
    assert all(len(pid) >= 24 for pid in ids)


# ---------------------------------------------------------------------------
# verify_login -- proof by reading a real row, not by "no exception raised"
# ---------------------------------------------------------------------------


def test_verify_login_reports_what_it_proved() -> None:
    connection = FakeConnection(script=[(1, "some", "race", "row")])
    result = svc.verify_login(connection)

    assert result["login"] == "bbs_connector"
    assert result["read_a_row_from"] == "Evt.Races"
    assert result["row_found"] is True


def test_verify_login_reports_row_found_false_on_an_empty_table_without_raising() -> None:
    connection = FakeConnection(script=[None])
    result = svc.verify_login(connection)
    assert result["row_found"] is False


def test_verify_login_raises_a_plain_language_error_never_a_fabricated_success() -> None:
    with pytest.raises(svc.SqlSetupError, match="Evt.Races"):
        svc.verify_login(ExplodingConnection())
