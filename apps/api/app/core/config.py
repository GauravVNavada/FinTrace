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
    # Provider-specific credentials are the canonical configuration. The numbered
    # slots and AI_API_KEY remain compatibility fallbacks for existing deployments.
    gemini_api_key: str = ""
    groq_api_key: str = ""
    ai_api_key: str = ""
    gemini_api_key_1: str = ""
    gemini_api_key_2: str = ""
    groq_api_key_1: str = ""
    groq_api_key_2: str = ""
    ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    ai_model: str = "gemini-2.5-flash-lite"
    ai_fallback_provider: str = "groq"
    ai_fallback_api_key: str = ""
    ai_fallback_base_url: str = "https://api.groq.com/openai/v1"
    ai_fallback_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
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
        # Keep equivalent legacy names working, but never use a primary provider
        # credential as another provider's fallback credential.
        if not self.groq_base_url:
            self.groq_base_url = self.ai_fallback_base_url
        if self.ai_fallback_base_url == "https://api.groq.com/openai/v1":
            self.ai_fallback_base_url = self.groq_base_url
        if self.ai_fallback_model == "openai/gpt-oss-120b":
            self.ai_fallback_model = self.groq_model
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
            or not self.configured_ai_api_keys
        ):
            raise ValueError(
                "A configured live AI provider and provider-specific API key are required outside development"
            )
        return self

    @property
    def configured_ai_api_keys(self) -> tuple[str, ...]:
        return self._configured_provider_keys(self.ai_provider)

    @property
    def configured_ai_fallback_api_keys(self) -> tuple[str, ...]:
        return self._configured_provider_keys(self.ai_fallback_provider, include_legacy=True)

    def _configured_provider_keys(
        self, provider_name: str, *, include_legacy: bool = False
    ) -> tuple[str, ...]:
        provider_name = provider_name.casefold()
        provider_keys = {
            "gemini": (self.gemini_api_key, self.gemini_api_key_1, self.gemini_api_key_2),
            "google": (self.gemini_api_key, self.gemini_api_key_1, self.gemini_api_key_2),
            "groq": (self.groq_api_key, self.groq_api_key_1, self.groq_api_key_2),
        }.get(provider_name, ())
        legacy = (self.ai_fallback_api_key,) if include_legacy else ()
        if include_legacy and provider_keys:
            # Provider-specific configuration always wins over the compatibility
            # fallback, preventing a Gemini key from being sent to Groq.
            legacy = () if any(provider_keys) else legacy
        if not provider_keys and provider_name not in {"gemini", "google", "groq"}:
            legacy = (self.ai_api_key, *legacy)
        return tuple(dict.fromkeys(key for key in (*provider_keys, *legacy) if key))

    @property
    def resolved_ai_model(self) -> str:
        return self.groq_model if self.ai_provider.casefold() == "groq" else self.ai_model

    @property
    def resolved_ai_base_url(self) -> str:
        return self.groq_base_url if self.ai_provider.casefold() == "groq" else self.ai_base_url

    @property
    def resolved_ai_fallback_model(self) -> str:
        return self.groq_model if self.ai_fallback_provider.casefold() == "groq" else self.ai_model

    @property
    def resolved_ai_fallback_base_url(self) -> str:
        return (
            self.groq_base_url
            if self.ai_fallback_provider.casefold() == "groq"
            else self.ai_base_url
        )

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
