"""The read-only bbs_connector SQL account setup: plan, verify, apply.

Every "run SQL" path here is exercised against fake connections/cursors --
no real pyodbc or SQL Server needed. What's actually under test is the
logic: what gets reported, what gets generated, and -- most importantly --
that apply_plan() only ever runs what this module itself produced, and
that a login name or admin username can never break out of the SQL text
or connection string it gets interpolated into.
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


class ExplodingConnection:
    def cursor(self):
        raise RuntimeError("permission denied")


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


def test_password_charset_cannot_produce_a_character_that_would_break_generated_sql() -> None:
    """generate_password()'s own output can never be the thing that breaks
    a generated script or connection string -- the escaping elsewhere
    (T-SQL '' doubling, ODBC brace-quoting) is defense in depth for a
    hand-typed password, not something the generator relies on."""
    dangerous = set("'\"\\;{}[]")
    assert dangerous.isdisjoint(set(svc.PASSWORD_SYMBOLS))


# ---------------------------------------------------------------------------
# validate_login_name -- login_name flows straight into bracket-quoted SQL
# identifiers (CREATE LOGIN [name], etc.) in every function BBS itself
# uses to create/manage bbs_connector. This is the one thing standing
# between a malicious login_name and SQL injection into a generated
# script. NOT applied to administrator usernames (see
# sql_auth_connection_string tests below) -- those are never interpolated
# into SQL text, only into a connection string, where bracing is the
# correct defense instead.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["bbs_connector", "bbs_connector_test", "_leading_underscore", "A1", "x" * 128],
)
def test_validate_login_name_accepts_ordinary_names(name: str) -> None:
    assert svc.validate_login_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        "bbs_connector]",
        "bbs connector",  # a space
        "bbs_connector]; DROP LOGIN [sa",
        "bbs-connector",  # a hyphen
        "1starts_with_digit",
        "bbs_connector'",
        "x" * 129,  # too long
    ],
)
def test_validate_login_name_rejects_anything_outside_the_safe_charset(name: str) -> None:
    with pytest.raises(svc.SqlSetupError):
        svc.validate_login_name(name)


# ---------------------------------------------------------------------------
# Connection string building
# ---------------------------------------------------------------------------


def test_sql_auth_connection_string_carries_the_credentials() -> None:
    cs = svc.sql_auth_connection_string(
        host="localhost", instance="USABMX", database="RACE", user="bbs_connector", password="p@ss"
    )
    # user/password are brace-quoted (see _odbc_brace) -- a plain value
    # braces to itself with no functional difference.
    assert "UID={bbs_connector}" in cs
    assert "PWD={p@ss}" in cs
    assert "Trusted_Connection" not in cs
    assert "SERVER=localhost\\USABMX" in cs
    assert "DATABASE=RACE" in cs


def test_sql_auth_connection_string_without_an_instance() -> None:
    cs = svc.sql_auth_connection_string(
        host="sql.example", instance="", database="RACE", user="bbs_connector", password="x"
    )
    assert "SERVER=sql.example;" in cs


def test_sql_auth_connection_string_accepts_an_unusual_but_legitimate_admin_username() -> None:
    """The `user` parameter is also used for a SQL Server administrator
    account -- someone else's DBA may have named it anything, and it must
    not be forced through bbs_connector's restrictive naming rules."""
    cs = svc.sql_auth_connection_string(
        host="localhost", instance="", database="RACE", user="bmx-admin.sql", password="x"
    )
    assert "UID={bmx-admin.sql}" in cs


def test_sql_auth_connection_string_braces_a_password_that_would_otherwise_break_the_connection_string() -> (
    None
):
    """A manually typed password (an admin's, or a pasted-back existing
    one) is not restricted to any charset -- confirm a ';' or '}' in it
    can't inject or terminate connection string attributes early."""
    cs = svc.sql_auth_connection_string(
        host="localhost",
        instance="USABMX",
        database="RACE",
        user="bbs_connector",
        password="weird;UID=sa;PWD=known}pass",
    )
    # The whole password, semicolons and all, lands inside one braced
    # value with its own literal '}' doubled -- not split into separate
    # connection string attributes.
    assert "PWD={weird;UID=sa;PWD=known}}pass};" in cs


def test_sql_auth_connection_string_braces_a_malicious_admin_username_rather_than_rejecting_it() -> (
    None
):
    """An admin username is never validated against the login_name
    charset (see module docstring) -- it's connected-as, never
    interpolated into SQL text, so bracing alone is the correct and
    sufficient defense, not a name-format rejection."""
    cs = svc.sql_auth_connection_string(
        host="localhost",
        instance="",
        database="RACE",
        user="sa;DROP LOGIN [bbs_connector]",
        password="x",
    )
    assert "UID={sa;DROP LOGIN [bbs_connector]};" in cs


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


def test_connect_passes_an_integer_timeout_to_pyodbc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: pyodbc.connect()'s timeout kwarg maps to a C long
    (SQL_ATTR_LOGIN_TIMEOUT) and raises a bare TypeError on a real pyodbc
    build if given a float -- as this module's own code did before this
    test existed, turning every route that opens a connection into a raw
    500 instead of a reported connection failure. TypeError from bad
    argument types is not a pyodbc.Error (a distinct class, like on a
    real pyodbc build -- see test_connect_wraps_a_driver_error above),
    so connect()'s `except pyodbc.Error` must not catch or hide it."""

    class FakeError(Exception):
        pass

    class FakePyodbc:
        Error = FakeError

        @staticmethod
        def connect(connection_string, *, timeout, autocommit):
            if not isinstance(timeout, int) or isinstance(timeout, bool):
                raise TypeError("'float' object cannot be interpreted as an integer")
            return object()

    monkeypatch.setattr(svc, "pyodbc", FakePyodbc())
    svc.connect("DRIVER={x};SERVER=y;", timeout=5)  # must not raise
    with pytest.raises(TypeError):
        svc.connect("DRIVER={x};SERVER=y;", timeout=5.0)


# ---------------------------------------------------------------------------
# Local instance detection -- best-effort, never raises
# ---------------------------------------------------------------------------


def test_detect_local_sql_instances_returns_empty_without_winreg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "winreg", None)
    assert svc.detect_local_sql_instances() == []


def test_detect_local_sql_instances_returns_empty_when_the_key_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()

        @staticmethod
        def OpenKey(*_args, **_kwargs):
            raise OSError("not found")

    monkeypatch.setattr(svc, "winreg", FakeWinreg())
    assert svc.detect_local_sql_instances() == []


def test_detect_local_sql_instances_enumerates_real_values(monkeypatch: pytest.MonkeyPatch) -> None:
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
# login_exists -- decides create vs reset
# ---------------------------------------------------------------------------


def test_login_exists_true_when_found() -> None:
    connection = FakeConnection(script=[("bbs_connector",)])
    assert svc.login_exists(connection, "bbs_connector") is True


def test_login_exists_false_when_not_found() -> None:
    connection = FakeConnection(script=[None])
    assert svc.login_exists(connection, "bbs_connector") is False


def test_login_exists_uses_a_parameterized_query() -> None:
    connection = FakeConnection(script=[None])
    svc.login_exists(connection, "bbs_connector_test")
    sql, params = connection.executed[0]
    assert "sys.sql_logins" in sql
    assert params == ("bbs_connector_test",)


def test_login_exists_rejects_a_malicious_login_name() -> None:
    connection = FakeConnection(script=[])
    with pytest.raises(svc.SqlSetupError):
        svc.login_exists(connection, "bbs_connector]; DROP LOGIN [sa")
    assert connection.executed == []


# ---------------------------------------------------------------------------
# check_login_management_rights -- gates the admin-credentials path
# before it ever attempts CREATE/ALTER LOGIN
# ---------------------------------------------------------------------------


def test_check_login_management_rights_true_when_the_account_can_manage_logins() -> None:
    """Covers both sysadmin and the narrower ALTER ANY LOGIN permission --
    the query combines them into one yes/no via CASE WHEN, so from the
    caller's side (and this test's) both look identical: a bare 1."""
    connection = FakeConnection(script=[(1,)])
    assert svc.check_login_management_rights(connection) is True


def test_check_login_management_rights_false_for_a_read_only_account() -> None:
    connection = FakeConnection(script=[(0,)])
    assert svc.check_login_management_rights(connection) is False


def test_check_login_management_rights_never_touches_anything() -> None:
    connection = FakeConnection(script=[(0,)])
    svc.check_login_management_rights(connection)
    for sql, _params in connection.executed:
        assert sql.strip().upper().startswith("SELECT")


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


def test_create_plan_reset_plan_and_cleanup_sql_all_honor_a_custom_login_name() -> None:
    """login_name is a testing aid (see docs/setup-wizard.md's "Testing
    aids" section) so a throwaway login can be created, verified, and
    dropped without ever touching the real bbs_connector login."""
    create = svc.build_create_plan(database="RACE", login_name="bbs_connector_test")
    reset = svc.build_reset_password_plan(database="RACE", login_name="bbs_connector_test")
    cleanup = svc.build_cleanup_sql(database="RACE", login_name="bbs_connector_test")

    assert "[bbs_connector_test]" in create.sql
    assert "[bbs_connector]" not in create.sql
    assert "[bbs_connector_test]" in reset.sql
    assert "DROP LOGIN [bbs_connector_test]" in cleanup


def test_create_plan_rejects_a_malicious_login_name_instead_of_interpolating_it() -> None:
    with pytest.raises(svc.SqlSetupError):
        svc.build_create_plan(database="RACE", login_name="bbs_connector]; DROP LOGIN [sa")


def test_reset_password_plan_rejects_a_malicious_login_name_instead_of_interpolating_it() -> None:
    with pytest.raises(svc.SqlSetupError):
        svc.build_reset_password_plan(database="RACE", login_name="bbs_connector]; DROP LOGIN [sa")


def test_cleanup_sql_rejects_a_malicious_login_name_instead_of_interpolating_it() -> None:
    with pytest.raises(svc.SqlSetupError):
        svc.build_cleanup_sql(database="RACE", login_name="bbs_connector]; DROP LOGIN [sa")


# ---------------------------------------------------------------------------
# build_offline_create_plan -- the "hand it to a DBA" path: never assumes
# an answer to "does this login already exist"
# ---------------------------------------------------------------------------


def test_offline_create_plan_guards_every_step_with_if_not_exists() -> None:
    plan = svc.build_offline_create_plan(database="RACE")

    assert plan.kind == "create_if_missing"
    assert "IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'bbs_connector')" in plan.sql
    assert "IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'bbs_connector')" in plan.sql
    assert "CREATE LOGIN [bbs_connector]" in plan.sql
    assert "CREATE USER [bbs_connector] FOR LOGIN [bbs_connector]" in plan.sql
    assert "ALTER ROLE db_datareader ADD MEMBER [bbs_connector]" in plan.sql
    assert plan.password in plan.sql


def test_offline_create_plan_honors_a_custom_login_name() -> None:
    plan = svc.build_offline_create_plan(database="RACE", login_name="bbs_connector_test")
    assert "bbs_connector_test" in plan.sql
    assert "[bbs_connector]" not in plan.sql


def test_offline_create_plan_escapes_a_password_containing_a_single_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(svc, "generate_password", lambda: "Ab1!Ab1!Ab1!Ab1!Ab1!O'Ab")
    plan = svc.build_offline_create_plan(database="RACE")
    assert "O''Ab" in plan.sql
    assert plan.password == "Ab1!Ab1!Ab1!Ab1!Ab1!O'Ab"


def test_offline_create_plan_rejects_a_malicious_login_name_instead_of_interpolating_it() -> None:
    with pytest.raises(svc.SqlSetupError):
        svc.build_offline_create_plan(database="RACE", login_name="bbs_connector]; DROP LOGIN [sa")


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


def test_apply_plan_refuses_an_offline_create_if_missing_plan() -> None:
    """build_offline_create_plan()'s BEGIN...END blocks would be torn apart
    into invalid fragments by apply_plan's naive ';'-splitter -- it's
    copy/paste-only, meant for the operator's own tool (SSMS, sqlcmd) to
    run as a single batch. No route wires it up this way today; this is
    the structural guardrail in case that ever changes."""
    plan = svc.build_offline_create_plan(database="RACE")
    connection = FakeConnection(script=[])

    with pytest.raises(svc.SqlSetupError):
        svc.apply_plan(connection, plan)

    assert connection.executed == []


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


def test_verify_login_reports_a_custom_login_name() -> None:
    connection = FakeConnection(script=[(1, "some", "race", "row")])
    result = svc.verify_login(connection, login_name="bbs_connector_test")
    assert result["login"] == "bbs_connector_test"
