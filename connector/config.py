"""Track-agnostic environment configuration for the BBS Connector."""

from functools import lru_cache
import os
from pathlib import Path
import sys

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


APPLICATION_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_DATA_DIRECTORY = Path("BMX Broadcast Suite") / "UserData"


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
    app_version: str = "1.2.16"
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
    ):
        value = Path(getattr(settings, field))
        if not value.is_absolute():
            setattr(settings, field, root / value)
    return settings


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
