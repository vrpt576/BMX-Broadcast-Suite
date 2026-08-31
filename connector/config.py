"""Track-agnostic environment configuration for the BBS Connector."""

from functools import lru_cache
import os
from pathlib import Path
import sys

from pydantic import Field, TypeAdapter, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


APPLICATION_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_DATA_DIRECTORY = Path("BMX Broadcast Suite") / "UserData"
VALID_SQORZ_MODES = ("internet", "lan", "file")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def is_windows_program_files_install() -> bool:
    """Return whether this code is running from a Windows Program Files tree."""
    if sys.platform != "win32":
        return False
    roots = {
        value
        for value in (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
        )
        if value
    }
    return any(_is_relative_to(APPLICATION_ROOT, Path(root)) for root in roots)


def windows_user_data_root() -> Path:
    """Return the machine-wide writable BBS data directory."""
    override = os.environ.get("BBS_RUNTIME_ROOT")
    if override:
        return Path(override).expanduser()
    program_data = os.environ.get("ProgramData")
    if not program_data:
        raise RuntimeError("ProgramData is unavailable for this Windows installation.")
    return Path(program_data) / WINDOWS_DATA_DIRECTORY


def configuration_file() -> Path:
    """Select the local development or installed-machine configuration file."""
    override = os.environ.get("BBS_ENV_FILE")
    if override:
        return Path(override).expanduser()
    if is_windows_program_files_install():
        return windows_user_data_root() / ".env"
    return Path(".env")


def runtime_root() -> Path:
    """Return the base directory for mutable logs, state, caches, and themes."""
    override = os.environ.get("BBS_RUNTIME_ROOT")
    if override:
        return Path(override).expanduser()
    if is_windows_program_files_install():
        return windows_user_data_root()
    return Path.cwd()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BBS_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "BMX Broadcast Suite Connector"
    app_version: str = "1.3.2"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    log_dir: Path = Path("connector/logs")
    log_retention_days: int = 14
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    public_base_url: str = ""
    track_name: str = "BMX Track"
    default_theme: str = "default"

    sql_host: str = "localhost"
    sql_instance: str = ""
    sql_port: int | None = 1433
    sql_database: str = "RACE"
    sql_user: str = "bbs_connector"
    sql_password: str = Field(default="", repr=False)
    sql_driver: str = "ODBC Driver 18 for SQL Server"
    sql_encrypt: bool = True
    sql_trust_server_certificate: bool = True
    sql_connect_timeout: int = 2
    sql_query_timeout: int = 5

    cors_origins: str = ""
    remote_control_enabled: bool = False
    control_token: str = Field(default="", repr=False)
    remote_admin_enabled: bool = False
    admin_token: str = Field(default="", repr=False)
    current_moto_state_file: Path = Path("data/current_moto.json")
    current_moto_default: int = 1
    lineup_cache_file: Path = Path("data/last_known_lineup.json")
    results_cache_file: Path = Path("data/last_known_results.json")
    results_roll_state_file: Path = Path("data/results_roll.json")
    phase_override_file: Path = Path("data/race_phase_overrides.json")
    theme_dir: Path = Path("themes")

    # Optional Sqorz live-timing integration. Disabled by default; no auth,
    # so none of these are secrets, but they're still kept out of logs like
    # everything else in this class.
    sqorz_enabled: bool = False
    sqorz_mode: str = "internet"
    sqorz_event_id: str = ""
    sqorz_org_code: str = ""
    sqorz_host: str = ""
    sqorz_port: int = 4343
    sqorz_file_path: str = ""
    # None = mode-aware default (10s internet, 2s LAN -- see
    # sqorz_effective_poll_seconds). An explicit value always wins.
    sqorz_poll_seconds: int | None = None
    sqorz_timeout_seconds: float = 2.0
    sqorz_class_alias_file: Path = Path("data/sqorz_class_aliases.json")
    # LAN mode only: where the raw response is saved when it can't be parsed
    # into any usable rider data -- see SqorzService._fetch_lan().
    sqorz_lan_raw_response_file: Path = Path("data/sqorz_lan_last_response.json")

    # Sqorz-only mode: an explicit override for a track that has both
    # RaceManager and Sqorz configured but wants Sqorz-only anyway. Every
    # other case (RaceManager present, or absent with Sqorz configured) is
    # detected automatically -- see operating_mode_service.py.
    force_sqorz_only_mode: bool = False
    sqorz_current_race_state_file: Path = Path("data/sqorz_current_race.json")

    # A bare `NAME=` in .env (exactly what .env.example ships for several of
    # these, and what ConfigurationService.save() writes when a field is
    # cleared) is read by pydantic-settings as the literal string "". For
    # every field below except the plain str ones, that used to fail type
    # validation and crash BBS at startup before FastAPI even loaded --
    # confirmed live during the pre-trip rehearsal for
    # BBS_SQORZ_POLL_SECONDS, and true of every other non-str field here for
    # the same reason (a bool/int/float/Path field has no valid parse of "").
    # A typo'd, non-blank value (e.g. BBS_APP_PORT=80e0) is exactly as real a
    # risk and must not crash the whole connector either -- RaceManager, the
    # Director, and the existing overlays must still come up even if one
    # setting's own value is broken. Both cases fall back to this field's own
    # declared default; a non-blank value that still doesn't parse also
    # prints a startup-time warning naming the setting and the bad value, so
    # a real typo is loud (in the console, not silently swallowed) without
    # being fatal.
    #
    # BBS_SQL_PORT is deliberately in this list: a named SQL instance
    # (BBS_SQL_INSTANCE, e.g. connecting as HOST\USABMX) takes precedence
    # over a TCP port -- see the `sql_server` property below, untouched by
    # this validator -- and the documented way to use a named instance is to
    # leave BBS_SQL_PORT blank. That must not crash startup either. This
    # validator only decides what value sql_port itself resolves to; it does
    # not change sql_server's own instance-vs-port precedence logic.
    @field_validator(
        "sqorz_enabled",
        "sqorz_port",
        "sqorz_poll_seconds",
        "sqorz_timeout_seconds",
        "sqorz_class_alias_file",
        "sqorz_lan_raw_response_file",
        "force_sqorz_only_mode",
        "sqorz_current_race_state_file",
        "sql_port",
        "sql_connect_timeout",
        "sql_query_timeout",
        "app_port",
        "sql_encrypt",
        "sql_trust_server_certificate",
        "log_retention_days",
        "remote_control_enabled",
        "remote_admin_enabled",
        "current_moto_default",
        mode="before",
    )
    @classmethod
    def _blank_or_unparseable_value_falls_back_to_default(
        cls, value: object, info: ValidationInfo
    ) -> object:
        if not isinstance(value, str):
            return value
        default = cls.model_fields[info.field_name].default
        if value.strip() == "":
            return default
        try:
            TypeAdapter(cls.model_fields[info.field_name].annotation).validate_python(value)
        except ValidationError:
            print(
                f"WARNING: BBS_{info.field_name.upper()}={value!r} is not a valid value "
                f"-- falling back to the default ({default!r}).",
                file=sys.stderr,
            )
            return default
        return value

    @field_validator("sqorz_mode", mode="before")
    @classmethod
    def _blank_or_unrecognised_sqorz_mode_falls_back_to_internet(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        if normalized == "":
            return "internet"
        if normalized not in VALID_SQORZ_MODES:
            print(
                f"WARNING: BBS_SQORZ_MODE={value!r} is not one of "
                f"{VALID_SQORZ_MODES} -- falling back to 'internet'.",
                file=sys.stderr,
            )
            return "internet"
        return normalized

    @property
    def sqorz_effective_poll_seconds(self) -> float:
        if self.sqorz_poll_seconds is not None:
            return float(self.sqorz_poll_seconds)
        return 2.0 if self.sqorz_mode == "lan" else 10.0

    @property
    def sql_server(self) -> str:
        if self.sql_instance:
            return f"{self.sql_host}\\{self.sql_instance}"
        if self.sql_port:
            return f"{self.sql_host},{self.sql_port}"
        return self.sql_host

    @property
    def connection_string(self) -> str:
        values = {
            "DRIVER": f"{{{self.sql_driver}}}", "SERVER": self.sql_server,
            "DATABASE": self.sql_database, "UID": self.sql_user, "PWD": self.sql_password,
            "Encrypt": "yes" if self.sql_encrypt else "no",
            "TrustServerCertificate": "yes" if self.sql_trust_server_certificate else "no",
            "Application Name": self.app_name,
        }
        return ";".join(f"{key}={value}" for key, value in values.items()) + ";"

    @property
    def cors_origin_list(self) -> list[str]:
        configured = [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip() and origin.strip() != "*"
        ]
        if configured:
            return configured
        return [
            f"http://127.0.0.1:{self.app_port}",
            f"http://localhost:{self.app_port}",
        ]


@lru_cache
def get_settings() -> Settings:
    settings = Settings(_env_file=configuration_file())
    root = runtime_root()
    for field in (
        "log_dir",
        "current_moto_state_file",
        "lineup_cache_file",
        "results_cache_file",
        "results_roll_state_file",
        "phase_override_file",
        "theme_dir",
        "sqorz_class_alias_file",
        "sqorz_lan_raw_response_file",
        "sqorz_current_race_state_file",
    ):
        value = Path(getattr(settings, field))
        if not value.is_absolute():
            setattr(settings, field, root / value)
    return settings


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
