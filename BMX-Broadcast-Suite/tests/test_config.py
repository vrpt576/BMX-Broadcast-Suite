from connector.config import Settings


def test_connection_string_uses_configurable_server():
    settings=Settings(_env_file=None, sql_host='10.0.0.5', sql_instance='RACEMANAGER', sql_database='TRACKDB', sql_user='reader', sql_password='x')
    assert 'SERVER=10.0.0.5\\RACEMANAGER' in settings.connection_string
    assert 'DATABASE=TRACKDB' in settings.connection_string
    assert 'UID=reader' in settings.connection_string


def test_port_used_when_instance_is_blank():
    settings=Settings(_env_file=None, sql_host='db.local', sql_instance='', sql_port=1444)
    assert settings.sql_server == 'db.local,1444'
