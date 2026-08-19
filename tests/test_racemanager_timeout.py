"""Windows pyodbc compatibility regression coverage."""

from __future__ import annotations

from types import SimpleNamespace

import database.racemanager as module
from database.racemanager import RaceManagerDatabase


class FakeCursor:
    """Intentionally has no timeout attribute, matching pyodbc 5.2 Cursor."""

    description = [("ok",)]

    def execute(self, query, params):
        assert query == "SELECT 1 AS ok"
        assert params == ()

    def fetchall(self):
        return [(1,)]


class FakeConnection:
    def __init__(self) -> None:
        self.timeout = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor()

    def close(self) -> None:
        self.closed = True


def test_query_timeout_is_applied_without_cursor_timeout(monkeypatch) -> None:
    connection = FakeConnection()
    fake_pyodbc = SimpleNamespace(
        Error=Exception,
        connect=lambda *_args, **kwargs: connection,
    )
    monkeypatch.setattr(module, "pyodbc", fake_pyodbc)

    rows = RaceManagerDatabase(
        "Driver=fake",
        connect_timeout=2,
        query_timeout=5,
    ).fetch_all("SELECT 1 AS ok")

    assert rows == [{"ok": 1}]
    assert connection.timeout == 5
    # Pooled: a successful query returns the connection for reuse rather
    # than closing it.
    assert connection.closed is False


def test_successful_queries_reuse_the_pooled_connection(monkeypatch) -> None:
    connections = []

    def fake_connect(*_args, **_kwargs):
        connection = FakeConnection()
        connections.append(connection)
        return connection

    fake_pyodbc = SimpleNamespace(Error=Exception, connect=fake_connect)
    monkeypatch.setattr(module, "pyodbc", fake_pyodbc)

    database = RaceManagerDatabase("Driver=fake", connect_timeout=2, query_timeout=5)
    database.fetch_all("SELECT 1 AS ok")
    database.fetch_all("SELECT 1 AS ok")

    assert len(connections) == 1
    assert connections[0].closed is False


def test_failed_query_discards_the_connection_instead_of_reusing_it(monkeypatch) -> None:
    connections = []

    def fake_connect(*_args, **_kwargs):
        connection = FakeConnection()
        connections.append(connection)
        return connection

    fake_pyodbc = SimpleNamespace(Error=Exception, connect=fake_connect)
    monkeypatch.setattr(module, "pyodbc", fake_pyodbc)

    database = RaceManagerDatabase("Driver=fake", connect_timeout=2, query_timeout=5)

    class FailingCursor(FakeCursor):
        def execute(self, query, params):
            raise RuntimeError("connection reset")

    connections_seen = []

    def fake_connect_with_failure(*_args, **_kwargs):
        connection = FakeConnection()
        connection.cursor = lambda: FailingCursor()
        connections_seen.append(connection)
        return connection

    monkeypatch.setattr(fake_pyodbc, "connect", fake_connect_with_failure)

    try:
        database.fetch_all("SELECT 1 AS ok")
    except Exception:
        pass

    assert connections_seen[0].closed is True

    # A subsequent call must open a fresh connection rather than reuse the
    # broken one.
    monkeypatch.setattr(fake_pyodbc, "connect", fake_connect)
    rows = database.fetch_all("SELECT 1 AS ok")
    assert rows == [{"ok": 1}]
    assert len(connections) == 1
    assert connections[0] is not connections_seen[0]
