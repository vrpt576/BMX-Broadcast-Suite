from connector.config import Settings
from connector.services.configuration_service import ConfigurationService


def test_generic_defaults_are_track_agnostic():
    s=Settings(_env_file=None)
    assert s.sql_host == 'localhost'
    assert s.sql_instance == ''
    assert s.default_theme == 'default'


def test_public_config_hides_password():
    s=Settings(
        _env_file=None,
        sql_password='secret',
        control_token='control-secret',
        admin_token='admin-secret',
    )
    data=ConfigurationService().get_public(s)
    assert data['sql_password'] == ''
    assert data['sql_password_configured'] is True
    assert 'secret' not in str(data)


def test_broadcast_public_config_exposes_no_database_or_access_details():
    s=Settings(
        _env_file=None,
        track_name='Example BMX',
        default_theme='example',
        public_base_url='http://bbs:8000',
        sql_host='private-db',
        sql_user='private-user',
        sql_password='private-password',
        control_token='control-secret',
        admin_token='admin-secret',
    )

    data=ConfigurationService().get_broadcast_public(s)

    assert data == {
        'track_name': 'Example BMX',
        'default_theme': 'example',
        'public_base_url': 'http://bbs:8000',
    }
    serialized=str(data)
    assert 'private' not in serialized
    assert 'secret' not in serialized
