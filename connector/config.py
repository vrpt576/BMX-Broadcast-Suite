"""Environment-based configuration for the BBS Connector."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BBS_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "BMX Broadcast Suite Connector"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    log_level: str = "INFO"

    sql_host: str = "192.168.2.52"
    sql_instance: str = "USABMX"
    sql_port: int | None = None
    sql_database: str = "RACE"
    sql_user: str = "bbs_connector"
    sql_password: str = Field(default="", repr=False)
    sql_driver: str = "ODBC Driver 18 for SQL Server"
    sql_encrypt: bool = True
    sql_trust_server_certificate: bool = True
    sql_connect_timeout: int = 5
    sql_query_timeout: int = 10

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

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
            "DRIVER": f"{{{self.sql_driver}}}",
            "SERVER": self.sql_server,
            "DATABASE": self.sql_database,
            "UID": self.sql_user,
            "PWD": self.sql_password,
            "Encrypt": "yes" if self.sql_encrypt else "no",
            "TrustServerCertificate": (
                "yes" if self.sql_trust_server_certificate else "no"
            ),
            "Application Name": "BMX Broadcast Suite Connector",
        }
        return ";".join(f"{key}={value}" for key, value in values.items()) + ";"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
