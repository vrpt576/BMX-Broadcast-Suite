"""Status helpers shared by the Linux and Windows tray applications."""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ServiceStatus:
    service: str
    api: str
    database: str
    version: str | None = None
    moto_number: int | None = None
    race_phase: str | None = None
    class_name: str | None = None
    detail: str | None = None

    @property
    def healthy(self) -> bool:
        return self.service == "running" and self.api == "available" and self.database == "connected"


def systemd_state(unit: str = "bbs-connector.service") -> str:
    """Return a small stable state value for a systemd unit."""
    result = subprocess.run(
        ["systemctl", "is-active", unit],
        check=False,
        capture_output=True,
        text=True,
    )
    state = result.stdout.strip()
    if state == "active":
        return "running"
    if state in {"activating", "reloading"}:
        return "starting"
    if state == "failed":
        return "failed"
    return "stopped"


def windows_task_state(task: str = "BMX Broadcast Suite") -> str:
    """Return a stable state for the Windows boot-time scheduled task."""
    escaped = task.replace("'", "''")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"(Get-ScheduledTask -TaskName '{escaped}' -ErrorAction SilentlyContinue).State.ToString()",
        ],
        check=False,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        return "stopped"
    state = result.stdout.strip().lower()
    if state == "running":
        return "running"
    if state in {"queued"}:
        return "starting"
    return "stopped"


def service_state(service_name: str | None = None) -> str:
    """Read the native background runner state for the current platform."""
    if platform.system() == "Windows":
        return windows_task_state(service_name or "BMX Broadcast Suite")
    return systemd_state(service_name or "bbs-connector.service")


def _get_json(url: str, timeout: float = 2.5) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "BBS-Tray/1.2.4"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def read_status(base_url: str = "http://127.0.0.1:8000", unit: str | None = None) -> ServiceStatus:
    """Read the platform runner and connector's compact status endpoint."""
    service = service_state(unit)
    if service != "running":
        return ServiceStatus(service=service, api="unavailable", database="unknown")

    try:
        payload = _get_json(f"{base_url.rstrip('/')}/api/status")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return ServiceStatus(
            service=service,
            api="unavailable",
            database="unknown",
            detail=str(exc),
        )

    return ServiceStatus(
        service=service,
        api="available",
        database=str(payload.get("database", "unknown")),
        version=payload.get("version"),
        moto_number=payload.get("moto_number"),
        race_phase=payload.get("race_phase"),
        class_name=payload.get("class_name"),
    )


def status_lines(status: ServiceStatus) -> list[str]:
    """Render compact human-readable tray status lines."""
    lines = [f"Service: {status.service.title()}"]
    if status.api == "available":
        lines.append(f"RaceManager: {status.database.title()}")
    else:
        lines.append("Connector API: Unavailable")
    if status.moto_number is not None:
        label = f"Moto {status.moto_number}"
        if status.class_name:
            label += f" — {status.class_name}"
        lines.append(label)
    return lines
