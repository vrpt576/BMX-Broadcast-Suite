"""SQL Server connector for USABMX RaceManager.

This module provides a small helper class to connect to a RaceManager SQL Server
instance, query the current event, and fetch moto data.
"""

from typing import Any, Dict, List, Optional

try:
    import pyodbc
except ImportError as exc:
    raise ImportError(
        "pyodbc is required for RaceManager SQL Server access. "
        "Install it with `pip install pyodbc`."
    ) from exc


class RaceManagerConnector:
    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        database: str = "RaceManager",
        instance: Optional[str] = None,
        driver: str = "{ODBC Driver 17 for SQL Server}",
        trust_server_certificate: bool = True,
    ) -> None:
        self.host = host
        self.instance = instance
        self.user = user
        self.password = password
        self.database = database
        self.driver = driver
        self.trust_server_certificate = trust_server_certificate
        self.connection: Optional[pyodbc.Connection] = None

    def _build_connection_string(self) -> str:
        if not self.host:
            raise ValueError("SQL Server hostname is required.")
        if not self.user or not self.password:
            raise ValueError("SQL Server username and password are required.")

        server_name = f"{self.host}\\{self.instance}" if self.instance else self.host
        trust_value = "yes" if self.trust_server_certificate else "no"

        return (
            f"DRIVER={self.driver};"
            f"SERVER={server_name};"
            f"DATABASE={self.database};"
            f"UID={self.user};"
            f"PWD={self.password};"
            f"TrustServerCertificate={trust_value};"
        )

    def connect(self, timeout: int = 5) -> None:
        """Open a connection to the RaceManager SQL Server database."""
        conn_str = self._build_connection_string()

        try:
            self.connection = pyodbc.connect(conn_str, timeout=timeout)
        except pyodbc.Error as exc:
            raise ConnectionError(
                f"Could not connect to SQL Server at {self.host}: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Close the database connection if it is open."""
        if self.connection:
            try:
                self.connection.close()
            finally:
                self.connection = None

    def _execute_query(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        if not self.connection:
            raise ConnectionError("Database connection is not established.")

        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            columns = [column[0] for column in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except pyodbc.Error as exc:
            raise RuntimeError(f"SQL query failed: {exc}") from exc
        finally:
            cursor.close()

    def query_current_event(self) -> Optional[Dict[str, Any]]:
        """Query the current active event from the RaceManager database."""
        query = """
            SELECT TOP 1 EventID, EventName, EventDate, Location
            FROM Events
            WHERE IsActive = 1
            ORDER BY EventDate DESC
        """

        results = self._execute_query(query)
        return results[0] if results else None

    def query_moto_data(self, event_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query moto data for a specific event or the current event."""
        if event_id is None:
            event = self.query_current_event()
            if not event:
                return []
            event_id = event.get("EventID")

        query = """
            SELECT
                MotoID,
                ClassName,
                RoundName,
                HeatNumber,
                RiderName,
                RiderNumber,
                GateAssignment,
                Lane
            FROM Motos
            WHERE EventID = ?
            ORDER BY RoundName, HeatNumber, GateAssignment
        """

        return self._execute_query(query, [event_id])


__all__ = ["RaceManagerConnector"]
