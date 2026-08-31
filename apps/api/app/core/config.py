from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FinTrace API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql://fintrace:fintrace@localhost:55432/fintrace"
    storage_backend: str = "demo"
    migrations_dir: str = "migrations"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ]
    log_level: str = "INFO"
    ai_provider: str = "gemini"
    ai_api_key: str = ""
    gemini_api_key_1: str = ""
    gemini_api_key_2: str = ""
    groq_api_key_1: str = ""
    groq_api_key_2: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gemini-2.5-flash"
    ai_fallback_provider: str = ""
    ai_fallback_api_key: str = ""
    ai_fallback_base_url: str = "https://api.groq.com/openai/v1"
    ai_fallback_model: str = "openai/gpt-oss-120b"
    ai_timeout_seconds: float = 20.0
    auth_mode: str = "development"
    auth_secret: str = "fintrace-development-only-secret"
    auth_issuer: str = "fintrace"
    auth_audience: str = "fintrace-web"
    auth_clock_skew_seconds: int = 30
    upload_directory: str = "data/uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    max_upload_uncompressed_bytes: int = 50 * 1024 * 1024
    max_upload_zip_members: int = 2_000
    max_upload_rows: int = 100_000
    max_upload_columns: int = 200
    rate_limit_window_seconds: int = 60
    rate_limit_requests: int = 120

    @model_validator(mode="after")
    def validate_release_security(self) -> "Settings":
        self.app_env = self.app_env.casefold()
        self.auth_mode = self.auth_mode.casefold()
        if not self.ai_api_key:
            provider_keys = {
                "gemini": (self.gemini_api_key_1, self.gemini_api_key_2),
                "google": (self.gemini_api_key_1, self.gemini_api_key_2),
                "groq": (self.groq_api_key_1, self.groq_api_key_2),
            }.get(self.ai_provider.casefold(), ())
            self.ai_api_key = next((key for key in provider_keys if key), "")
        if self.auth_mode == "required" and (
            self.auth_secret == "fintrace-development-only-secret" or len(self.auth_secret) < 32
        ):
            raise ValueError(
                "AUTH_SECRET must be a long, non-default secret when AUTH_MODE=required"
            )
        if self.app_env in {"staging", "production"} and self.auth_mode != "required":
            raise ValueError("AUTH_MODE=required is mandatory outside development")
        if self.app_env in {"staging", "production"} and (
            self.ai_provider.casefold() in {"stub", "offline", "deterministic"}
            or not self.ai_api_key
        ):
            raise ValueError(
                "A configured live AI provider and AI_API_KEY are required outside development"
            )
        return self

    @property
    def configured_ai_api_keys(self) -> tuple[str, ...]:
        return self._configured_provider_keys(self.ai_provider, self.ai_api_key)

    @property
    def configured_ai_fallback_api_keys(self) -> tuple[str, ...]:
        return self._configured_provider_keys(self.ai_fallback_provider, self.ai_fallback_api_key)

    def _configured_provider_keys(self, provider_name: str, explicit_key: str) -> tuple[str, ...]:
        provider_keys = {
            "gemini": (self.gemini_api_key_1, self.gemini_api_key_2),
            "google": (self.gemini_api_key_1, self.gemini_api_key_2),
            "groq": (self.groq_api_key_1, self.groq_api_key_2),
        }.get(provider_name.casefold(), ())
        return tuple(dict.fromkeys(key for key in (explicit_key, *provider_keys) if key))

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
