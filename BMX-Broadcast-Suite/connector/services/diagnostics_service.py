"""Installation and RaceManager connectivity diagnostics."""

from __future__ import annotations

import platform
import socket
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from connector.config import Settings
from database.racemanager import RaceManagerDatabase, RaceManagerDatabaseError, pyodbc


@dataclass
class DiagnosticCheck:
    key: str
    label: str
    status: str
    detail: str
    required: bool = True


class DiagnosticsService:
    def __init__(self, settings: Settings, database: RaceManagerDatabase) -> None:
        self.settings = settings
        self.database = database

    def run(self) -> dict[str, Any]:
        checks: list[DiagnosticCheck] = []
        checks.append(self._python_check())
        checks.append(self._pyodbc_check())
        checks.append(self._driver_check())
        checks.append(self._configuration_check())
        checks.append(self._network_check())
        checks.extend(self._database_checks())

        required = [check for check in checks if check.required]
        overall = "ok" if all(check.status == "ok" for check in required) else "attention"
        return {
            "status": overall,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "application": {
                "name": self.settings.app_name,
                "version": self.settings.app_version,
                "platform": platform.platform(),
                "python": platform.python_version(),
            },
            "configuration": {
                "sql_server": self.settings.sql_server,
                "sql_database": self.settings.sql_database,
                "sql_user": self.settings.sql_user,
                "sql_driver": self.settings.sql_driver,
                "password_configured": bool(self.settings.sql_password),
                "state_file": str(self.settings.current_moto_state_file),
            },
            "checks": [asdict(check) for check in checks],
        }

    def _python_check(self) -> DiagnosticCheck:
        supported = sys.version_info >= (3, 11)
        return DiagnosticCheck(
            "python",
            "Python runtime",
            "ok" if supported else "error",
            f"Python {platform.python_version()} ({'supported' if supported else 'Python 3.11+ required'})",
        )

    def _pyodbc_check(self) -> DiagnosticCheck:
        if pyodbc is None:
            return DiagnosticCheck("pyodbc", "pyodbc package", "error", "pyodbc is not installed.")
        return DiagnosticCheck("pyodbc", "pyodbc package", "ok", f"pyodbc {getattr(pyodbc, 'version', 'installed')}")

    def _driver_check(self) -> DiagnosticCheck:
        if pyodbc is None:
            return DiagnosticCheck("odbc_driver", "SQL Server ODBC driver", "error", "Cannot inspect drivers until pyodbc is installed.")
        drivers = list(pyodbc.drivers())
        found = self.settings.sql_driver in drivers
        detail = (
            f"Found {self.settings.sql_driver}."
            if found
            else f"Missing {self.settings.sql_driver}. Installed: {', '.join(drivers) or 'none'}"
        )
        return DiagnosticCheck("odbc_driver", "SQL Server ODBC driver", "ok" if found else "error", detail)

    def _configuration_check(self) -> DiagnosticCheck:
        if not self.settings.sql_password:
            return DiagnosticCheck("configuration", "Connector configuration", "error", "BBS_SQL_PASSWORD is not configured in .env.")
        return DiagnosticCheck("configuration", "Connector configuration", "ok", f"Configured for {self.settings.sql_user}@{self.settings.sql_server}/{self.settings.sql_database}.")

    def _network_check(self) -> DiagnosticCheck:
        host = self.settings.sql_host
        port = self.settings.sql_port or 1433
        try:
            with socket.create_connection((host, port), timeout=min(self.settings.sql_connect_timeout, 3)):
                pass
        except OSError as exc:
            return DiagnosticCheck(
                "network",
                "SQL Server network path",
                "warning",
                f"Could not open TCP {host}:{port}: {exc}. Named instances may use SQL Browser/dynamic ports.",
                required=False,
            )
        return DiagnosticCheck("network", "SQL Server network path", "ok", f"TCP {host}:{port} is reachable.", required=False)

    def _database_checks(self) -> list[DiagnosticCheck]:
        if pyodbc is None or not self.settings.sql_password:
            return [
                DiagnosticCheck("database", "RaceManager database login", "error", "Skipped until pyodbc, the ODBC driver, and password are configured."),
                DiagnosticCheck("event", "Current RaceManager event", "warning", "Skipped because the database is unavailable.", required=False),
            ]
        try:
            row = self.database.fetch_one("SELECT DB_NAME() AS database_name, SYSTEM_USER AS login_name, GETDATE() AS server_time")
        except RaceManagerDatabaseError as exc:
            return [
                DiagnosticCheck("database", "RaceManager database login", "error", str(exc)),
                DiagnosticCheck("event", "Current RaceManager event", "warning", "Skipped because the database login failed.", required=False),
            ]

        checks = [DiagnosticCheck("database", "RaceManager database login", "ok", f"Connected to {row.get('database_name') if row else self.settings.sql_database} as {row.get('login_name') if row else self.settings.sql_user}.")]
        try:
            event = self.database.fetch_one(
                """
                SELECT TOP 1 e.Event_Name AS event_name, mb.Motoboard_DBID AS motoboard_id,
                       mb.Total_Motos AS total_motos, mb.Total_Riders AS total_riders
                FROM Evt.Events AS e
                JOIN Evt.Races AS r ON r.Event_ID = e.Event_DBID
                JOIN MB.Motoboard AS mb ON mb.Race_ID = r.Race_DBID
                ORDER BY e.Date_Begin DESC, mb.Date_Maintenance DESC
                """
            )
        except RaceManagerDatabaseError as exc:
            checks.append(DiagnosticCheck("event", "Current RaceManager event", "warning", f"Database connected, but event discovery failed: {exc}", required=False))
            return checks

        if event is None:
            checks.append(DiagnosticCheck("event", "Current RaceManager event", "warning", "Connected, but no event with a motoboard was found.", required=False))
        else:
            checks.append(DiagnosticCheck("event", "Current RaceManager event", "ok", f"{event.get('event_name')} — {event.get('total_motos')} motos, {event.get('total_riders')} riders. Motoboard {event.get('motoboard_id')}.", required=False))
        return checks
