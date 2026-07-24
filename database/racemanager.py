"""Low-level, read-only SQL Server client for USABMX RaceManager."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

try:
    import pyodbc
except ImportError:  # pragma: no cover - enables tests without native ODBC
    pyodbc = None  # type: ignore[assignment]


class RaceManagerDatabaseError(RuntimeError):
    """Raised when RaceManager cannot be reached or queried."""


class RaceManagerDatabase:
    def __init__(
        self,
        connection_string: str,
        *,
        connect_timeout: int = 5,
        query_timeout: int = 10,
    ) -> None:
        self.connection_string = connection_string
        self.connect_timeout = connect_timeout
        self.query_timeout = query_timeout

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if pyodbc is None:
            raise RaceManagerDatabaseError(
                "pyodbc is not installed. Install connector requirements and an "
                "ODBC Driver for SQL Server."
            )
        try:
            connection = pyodbc.connect(
                self.connection_string,
                timeout=self.connect_timeout,
                autocommit=True,
            )
        except pyodbc.Error as exc:
            raise RaceManagerDatabaseError(f"SQL Server connection failed: {exc}") from exc

        try:
            yield connection
        finally:
            connection.close()

    def fetch_all(
        self, query: str, params: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        try:
            with self.connection() as connection:
                cursor = connection.cursor()
                cursor.timeout = self.query_timeout
                cursor.execute(query, tuple(params or ()))
                columns = [column[0] for column in cursor.description or ()]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except RaceManagerDatabaseError:
            raise
        except Exception as exc:
            raise RaceManagerDatabaseError(f"RaceManager query failed: {exc}") from exc

    def fetch_one(
        self, query: str, params: Sequence[Any] | None = None
    ) -> Mapping[str, Any] | None:
        rows = self.fetch_all(query, params)
        return rows[0] if rows else None
