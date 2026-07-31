from pathlib import Path

import connector.config as config
from connector.config import Settings


def test_connection_string_uses_configurable_server():
    settings=Settings(_env_file=None, sql_host='10.0.0.5', sql_instance='RACEMANAGER', sql_database='TRACKDB', sql_user='reader', sql_password='x')
    assert 'SERVER=10.0.0.5\\RACEMANAGER' in settings.connection_string
    assert 'DATABASE=TRACKDB' in settings.connection_string
    assert 'UID=reader' in settings.connection_string


def test_port_used_when_instance_is_blank():
    settings=Settings(_env_file=None, sql_host='db.local', sql_instance='', sql_port=1444)
    assert settings.sql_server == 'db.local,1444'


def test_program_files_install_uses_programdata_for_all_mutable_paths(
    monkeypatch, tmp_path: Path
):
    program_files = tmp_path / "Program Files"
    program_data = tmp_path / "ProgramData"
    application_root = program_files / "BMX Broadcast Suite"
    user_data = program_data / "BMX Broadcast Suite" / "UserData"
    user_data.mkdir(parents=True)
    (user_data / ".env").write_text(
        "\n".join(
            (
                "BBS_LOG_DIR=connector/logs",
                "BBS_CURRENT_MOTO_STATE_FILE=data/current_moto.json",
                "BBS_LINEUP_CACHE_FILE=data/last_valid_lineup.json",
                "BBS_RESULTS_CACHE_FILE=data/last_valid_results.json",
                "BBS_RESULTS_ROLL_STATE_FILE=data/results_roll.json",
                "BBS_THEME_DIR=themes",
            )
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setattr(config, "APPLICATION_ROOT", application_root)
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.setenv("ProgramData", str(program_data))
    monkeypatch.delenv("BBS_ENV_FILE", raising=False)
    monkeypatch.delenv("BBS_RUNTIME_ROOT", raising=False)
    config.get_settings.cache_clear()
    try:
        settings = config.get_settings()
        assert config.configuration_file() == user_data / ".env"
        assert settings.log_dir == user_data / "connector" / "logs"
        assert settings.current_moto_state_file == user_data / "data" / "current_moto.json"
        assert settings.lineup_cache_file == user_data / "data" / "last_valid_lineup.json"
        assert settings.results_cache_file == user_data / "data" / "last_valid_results.json"
        assert settings.results_roll_state_file == user_data / "data" / "results_roll.json"
        assert settings.theme_dir == user_data / "themes"
        for path in (
            settings.log_dir,
            settings.current_moto_state_file,
            settings.lineup_cache_file,
            settings.results_cache_file,
            settings.results_roll_state_file,
            settings.theme_dir,
        ):
            assert not str(path).startswith(str(application_root))
    finally:
        config.get_settings.cache_clear()
