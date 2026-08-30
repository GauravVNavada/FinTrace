from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FinTrace API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql://fintrace:fintrace@localhost:55432/fintrace"
    storage_backend: str = "demo"
    migrations_dir: str = "migrations"
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    log_level: str = "INFO"
    ai_provider: str = "stub"
    auth_mode: str = "development"
    auth_secret: str = "fintrace-development-only-secret"
    auth_issuer: str = "fintrace"
    auth_audience: str = "fintrace-web"
    auth_clock_skew_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
