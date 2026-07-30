import connector.service_status as service_status
from connector.service_status import ServiceStatus, status_lines


def test_healthy_service_status():
    status = ServiceStatus(
        service="running",
        api="available",
        database="connected",
        version="1.2.5",
        moto_number=12,
        class_name="8 Novice",
    )
    assert status.healthy is True
    assert status_lines(status) == [
        "Service: Running",
        "RaceManager: Connected",
        "Moto 12 — 8 Novice",
    ]


def test_stopped_service_status():
    status = ServiceStatus(service="stopped", api="unavailable", database="unknown")
    assert status.healthy is False
    assert status_lines(status) == ["Service: Stopped", "Connector API: Unavailable"]


def test_service_state_uses_windows_task(monkeypatch):
    monkeypatch.setattr(service_status.platform, "system", lambda: "Windows")
    monkeypatch.setattr(service_status, "windows_task_state", lambda name: f"windows:{name}")
    assert service_status.service_state("BMX Broadcast Suite") == "windows:BMX Broadcast Suite"


def test_service_state_uses_systemd_on_linux(monkeypatch):
    monkeypatch.setattr(service_status.platform, "system", lambda: "Linux")
    monkeypatch.setattr(service_status, "systemd_state", lambda name: f"linux:{name}")
    assert service_status.service_state("bbs-connector.service") == "linux:bbs-connector.service"


def test_windows_task_state_maps_running(monkeypatch):
    class Result:
        returncode = 0
        stdout = "Running\n"

    monkeypatch.setattr(service_status.subprocess, "run", lambda *args, **kwargs: Result())
    assert service_status.windows_task_state() == "running"


def test_windows_task_state_maps_missing_to_stopped(monkeypatch):
    class Result:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(service_status.subprocess, "run", lambda *args, **kwargs: Result())
    assert service_status.windows_task_state() == "stopped"
