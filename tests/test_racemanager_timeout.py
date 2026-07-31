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
    assert connection.closed is True
