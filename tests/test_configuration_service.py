from pathlib import Path

import pytest

from connector.config import Settings, get_settings
from connector.services.configuration_service import ConfigurationService


def test_generic_defaults_are_track_agnostic():
    s=Settings(_env_file=None)
    assert s.sql_host == 'localhost'
    assert s.sql_instance == ''
    assert s.default_theme == 'default'


def test_sqorz_poll_seconds_defaults_by_mode_when_unset():
    assert Settings(_env_file=None, sqorz_mode='internet').sqorz_effective_poll_seconds == 10.0
    assert Settings(_env_file=None, sqorz_mode='lan').sqorz_effective_poll_seconds == 2.0


def test_sqorz_poll_seconds_explicit_value_overrides_the_mode_aware_default():
    settings = Settings(_env_file=None, sqorz_mode='lan', sqorz_poll_seconds=7)
    assert settings.sqorz_effective_poll_seconds == 7.0


@pytest.fixture
def isolated_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    env_file = tmp_path / '.env'
    monkeypatch.setenv('BBS_ENV_FILE', str(env_file))
    yield env_file
    get_settings.cache_clear()


def test_leaving_poll_seconds_blank_in_the_ui_stores_no_key_not_an_empty_one(
    isolated_env_file: Path,
) -> None:
    settings = ConfigurationService().save({'sqorz_mode': 'lan', 'sqorz_poll_seconds': ''})

    assert settings.sqorz_poll_seconds is None
    assert settings.sqorz_effective_poll_seconds == 2.0
    # An empty BBS_SQORZ_POLL_SECONDS= would fail to parse as int on the next
    # load -- the key must be absent entirely, not present-and-blank.
    assert 'BBS_SQORZ_POLL_SECONDS' not in isolated_env_file.read_text(encoding='utf-8')


def test_setting_poll_seconds_explicitly_always_wins(isolated_env_file: Path) -> None:
    settings = ConfigurationService().save({'sqorz_poll_seconds': 7})

    assert settings.sqorz_poll_seconds == 7
    assert settings.sqorz_effective_poll_seconds == 7.0
    assert 'BBS_SQORZ_POLL_SECONDS=7' in isolated_env_file.read_text(encoding='utf-8')


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
