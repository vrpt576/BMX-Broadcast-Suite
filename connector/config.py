"""Track-agnostic environment configuration for the BBS Connector."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BBS_", case_sensitive=False, extra="ignore")

    app_name: str = "BMX Broadcast Suite Connector"
    app_version: str = "1.1.0"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    log_dir: Path = Path("connector/logs")
    log_retention_days: int = 14
    app_host: str = "0.0.0.0"
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
    sql_connect_timeout: int = 5
    sql_query_timeout: int = 10

    cors_origins: str = "*"
    current_moto_state_file: Path = Path("data/current_moto.json")
    current_moto_default: int = 1
    lineup_cache_file: Path = Path("data/last_known_lineup.json")

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
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
