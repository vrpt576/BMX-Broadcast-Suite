from connector.config import Settings


def test_named_instance_connection_string():
    settings = Settings(sql_password="secret")
    assert "SERVER=192.168.2.52\\USABMX" in settings.connection_string
    assert "DATABASE=RACE" in settings.connection_string
    assert "PWD=secret" in settings.connection_string
