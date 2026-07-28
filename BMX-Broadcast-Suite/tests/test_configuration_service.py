from pathlib import Path
from connector.config import Settings
from connector.services.configuration_service import ConfigurationService


def test_generic_defaults_are_track_agnostic():
    s=Settings(_env_file=None)
    assert s.sql_host == 'localhost'
    assert s.sql_instance == ''
    assert s.default_theme == 'default'


def test_public_config_hides_password():
    s=Settings(_env_file=None, sql_password='secret')
    data=ConfigurationService().get_public(s)
    assert data['sql_password'] == ''
    assert data['sql_password_configured'] is True
    assert 'secret' not in str(data)
