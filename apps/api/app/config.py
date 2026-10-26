from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://integrity_app:local_only_password@localhost:5432/integrity"
    jwt_secret: str = "local-development-secret-change-this-32-bytes-minimum"
    login_hash_secret: str = "local-login-hash-secret-change-before-production"
    access_token_minutes: int = 15
    cors_origins: str = "http://localhost:3000"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    @field_validator("jwt_secret")
    @classmethod
    def require_strong_secret(cls, value: str) -> str:
        if len(value.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.production and settings.jwt_secret.startswith("local-development"):
        raise ValueError("A production JWT_SECRET must be explicitly configured")
    if settings.production and settings.login_hash_secret.startswith("local-login-hash"):
        raise ValueError("A production LOGIN_HASH_SECRET must be explicitly configured")
    return settings


settings = get_settings()
