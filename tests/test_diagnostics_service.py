from connector.config import Settings
from connector.services.diagnostics_service import DiagnosticsService


class FakeDatabase:
    def fetch_one(self, query, params=None):
        if "DB_NAME" in query:
            return {"database_name": "RACE", "login_name": "bbs_connector"}
        return {"event_name": "Thursday Night Racing", "motoboard_id": "abc", "total_motos": 5, "total_riders": 17}


def test_diagnostics_reports_configuration_and_application(monkeypatch):
    settings = Settings(sql_password="secret")
    service = DiagnosticsService(settings, FakeDatabase())
    monkeypatch.setattr(service, "_driver_check", lambda: service._python_check())
    monkeypatch.setattr(service, "_network_check", lambda: service._python_check())
    result = service.run()
    assert result["application"]["version"] == "1.2.13"
    assert result["configuration"]["password_configured"] is True
    assert any(check["key"] == "database" for check in result["checks"])


def test_diagnostics_flags_missing_password(monkeypatch):
    settings = Settings(sql_password="")
    service = DiagnosticsService(settings, FakeDatabase())
    monkeypatch.setattr(service, "_driver_check", lambda: service._python_check())
    monkeypatch.setattr(service, "_network_check", lambda: service._python_check())
    result = service.run()
    config = next(check for check in result["checks"] if check["key"] == "configuration")
    assert config["status"] == "error"
    assert result["status"] == "attention"
