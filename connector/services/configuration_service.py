"""Safe read/write support for local BBS configuration."""
from __future__ import annotations

from typing import Any

from connector.config import (
    Settings,
    configuration_file,
    get_settings,
    reload_settings,
)

FIELDS = {
    'track_name':'BBS_TRACK_NAME','default_theme':'BBS_DEFAULT_THEME','app_host':'BBS_APP_HOST',
    'app_port':'BBS_APP_PORT','public_base_url':'BBS_PUBLIC_BASE_URL','sql_host':'BBS_SQL_HOST',
    'sql_instance':'BBS_SQL_INSTANCE','sql_port':'BBS_SQL_PORT','sql_database':'BBS_SQL_DATABASE',
    'sql_user':'BBS_SQL_USER','sql_password':'BBS_SQL_PASSWORD','sql_driver':'BBS_SQL_DRIVER',
    'sql_encrypt':'BBS_SQL_ENCRYPT','sql_trust_server_certificate':'BBS_SQL_TRUST_SERVER_CERTIFICATE',
    'sql_connect_timeout':'BBS_SQL_CONNECT_TIMEOUT','sql_query_timeout':'BBS_SQL_QUERY_TIMEOUT',
    'cors_origins':'BBS_CORS_ORIGINS','current_moto_state_file':'BBS_CURRENT_MOTO_STATE_FILE',
    'current_moto_default':'BBS_CURRENT_MOTO_DEFAULT','lineup_cache_file':'BBS_LINEUP_CACHE_FILE',
    'results_cache_file':'BBS_RESULTS_CACHE_FILE','results_roll_state_file':'BBS_RESULTS_ROLL_STATE_FILE',
    'remote_control_enabled':'BBS_REMOTE_CONTROL_ENABLED','control_token':'BBS_CONTROL_TOKEN',
    'remote_admin_enabled':'BBS_REMOTE_ADMIN_ENABLED','admin_token':'BBS_ADMIN_TOKEN',
    'sqorz_enabled':'BBS_SQORZ_ENABLED','sqorz_mode':'BBS_SQORZ_MODE',
    'sqorz_event_id':'BBS_SQORZ_EVENT_ID','sqorz_org_code':'BBS_SQORZ_ORG_CODE',
    'sqorz_host':'BBS_SQORZ_HOST','sqorz_port':'BBS_SQORZ_PORT',
    'sqorz_poll_seconds':'BBS_SQORZ_POLL_SECONDS','sqorz_timeout_seconds':'BBS_SQORZ_TIMEOUT_SECONDS',
}

class ConfigurationService:
    def get_broadcast_public(self, settings: Settings) -> dict[str, Any]:
        return {
            'track_name': settings.track_name,
            'default_theme': settings.default_theme,
            'public_base_url': settings.public_base_url,
        }

    def get_public(self, settings: Settings) -> dict[str, Any]:
        secret_fields = {'sql_password','control_token','admin_token'}
        data = {key: getattr(settings,key) for key in FIELDS if key not in secret_fields}
        data['sql_password_configured'] = bool(settings.sql_password)
        data['sql_password'] = ''
        data['control_token_configured'] = bool(settings.control_token)
        data['control_token'] = ''
        data['admin_token_configured'] = bool(settings.admin_token)
        data['admin_token'] = ''
        data['sqorz_effective_poll_seconds'] = settings.sqorz_effective_poll_seconds
        data['restart_required_for'] = [
            'app_host','app_port','cors_origins','remote_control_enabled',
            'control_token','remote_admin_enabled','admin_token'
        ]
        return data

    def save(self, values: dict[str, Any]) -> Settings:
        existing = self._read_env()
        for field, env_name in FIELDS.items():
            if field not in values:
                continue
            value = values[field]
            if field in {'sql_password','control_token','admin_token'} and (
                value is None or str(value) == ''
            ):
                continue
            if field == 'sqorz_poll_seconds' and value in (None, ''):
                # Unset, not blanked -- an empty string would fail to parse
                # as int on the next load. Absent means "mode-aware default"
                # (see Settings.sqorz_effective_poll_seconds).
                existing.pop(env_name, None)
                continue
            if field in {
                'app_port','sql_port','sql_connect_timeout','sql_query_timeout',
                'current_moto_default','sqorz_port','sqorz_poll_seconds',
            }:
                value = '' if value in (None,'') else str(int(value))
            elif field == 'sqorz_timeout_seconds':
                value = '' if value in (None,'') else str(float(value))
            elif field in {
                'sql_encrypt','sql_trust_server_certificate',
                'remote_control_enabled','remote_admin_enabled','sqorz_enabled',
            }:
                value = 'true' if bool(value) else 'false'
            else:
                value = str(value).strip()
            existing[env_name] = value
        self._write_env(existing)
        reload_settings()
        from connector.dependencies import get_database, get_sqorz_service
        get_database.cache_clear()
        get_sqorz_service.cache_clear()
        return get_settings()

    @staticmethod
    def _read_env() -> dict[str,str]:
        data: dict[str,str] = {}
        env_path = configuration_file()
        if env_path.exists():
            for raw in env_path.read_text(encoding='utf-8').splitlines():
                line=raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key,value=line.split('=',1)
                data[key.strip()]=value.strip()
        return data

    @staticmethod
    def _write_env(data: dict[str,str]) -> None:
        env_path = configuration_file()
        env_path.parent.mkdir(parents=True, exist_ok=True)
        lines=['# BMX Broadcast Suite local configuration','# Generated by /configuration. Do not commit this file.']
        lines += [f'{key}={value}' for key,value in sorted(data.items())]
        env_path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
