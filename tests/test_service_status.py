from connector.service_status import ServiceStatus, status_lines


def test_healthy_service_status():
    status = ServiceStatus(
        service="running",
        api="available",
        database="connected",
        version="1.2.3",
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
