"""Low-level, read-only SQL Server client for USABMX RaceManager."""

from __future__ import annotations

import queue
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

try:
    import pyodbc
except ImportError:  # pragma: no cover - enables tests without native ODBC
    pyodbc = None  # type: ignore[assignment]


class RaceManagerDatabaseError(RuntimeError):
    """Raised when RaceManager cannot be reached or queried."""


class RaceManagerDatabase:
    """Read-only RaceManager client backed by a small, reusable connection pool.

    Director status polling and independent overlay/lineup/results endpoints
    each query RaceManager on their own cadence, often over a WAN/Tailscale
    link. Opening and closing a new SQL connection per query added a full
    TCP handshake and SQL login to every call. Connections are now pooled and
    reused; a connection is only discarded and reconnected if it raised
    during use.
    """

    def __init__(
        self,
        connection_string: str,
        *,
        connect_timeout: int = 2,
        query_timeout: int = 5,
        pool_size: int = 4,
    ) -> None:
        self.connection_string = connection_string
        self.connect_timeout = connect_timeout
        self.query_timeout = query_timeout
        self.pool_size = pool_size
        self._pool: queue.LifoQueue[Any] = queue.LifoQueue(maxsize=pool_size)
        self._created = 0
        self._lock = threading.Lock()

    def _connect(self) -> Any:
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
            # pyodbc exposes query timeout on Connection on supported builds;
            # Cursor.timeout is not available in pyodbc 5.2 on Windows.
            if hasattr(connection, "timeout"):
                connection.timeout = self.query_timeout
        except pyodbc.Error as exc:
            raise RaceManagerDatabaseError(f"SQL Server connection failed: {exc}") from exc
        return connection

    def _acquire(self) -> Any:
        try:
            return self._pool.get_nowait()
        except queue.Empty:
            pass
        with self._lock:
            if self._created < self.pool_size:
                self._created += 1
                connect_now = True
            else:
                connect_now = False
        if connect_now:
            try:
                return self._connect()
            except Exception:
                with self._lock:
                    self._created -= 1
                raise
        # Pool is fully checked out; wait for a connection to be released.
        return self._pool.get()

    def _release(self, connection: Any, *, healthy: bool) -> None:
        if not healthy:
            try:
                connection.close()
            except Exception:
                pass
            with self._lock:
                self._created -= 1
            return
        try:
            self._pool.put_nowait(connection)
        except queue.Full:  # pragma: no cover - defensive, pool sizing guarantees room
            connection.close()
            with self._lock:
                self._created -= 1

    @contextmanager
    def connection(self) -> Iterator[Any]:
        connection = self._acquire()
        healthy = True
        try:
            yield connection
        except Exception:
            healthy = False
            raise
        finally:
            self._release(connection, healthy=healthy)

    def fetch_all(
        self, query: str, params: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        try:
            with self.connection() as connection:
                cursor = connection.cursor()
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

    def column_exists(self, schema: str, table: str, column: str) -> bool:
        """Return whether a column exists without selecting from that column."""
        row = self.fetch_one(
            """
            SELECT CASE WHEN COL_LENGTH(?, ?) IS NULL THEN 0 ELSE 1 END AS present;
            """,
            [f"{schema}.{table}", column],
        )
        return bool(row and row.get("present"))
