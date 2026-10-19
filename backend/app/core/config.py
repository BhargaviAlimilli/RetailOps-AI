from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="RETAILOPS_", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr | None = None
    demo_password: SecretStr | None = Field(default=None, min_length=12, max_length=256)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "[::1]"])
    database_timeout_seconds: float = Field(default=3, gt=0, le=30)

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("Database URL must use postgresql+psycopg")
        return value

    @field_validator("cors_origins")
    @classmethod
    def require_explicit_origins(cls, value: list[str]) -> list[str]:
        if any(origin == "*" or not origin.startswith(("http://", "https://")) for origin in value):
            raise ValueError("CORS origins must be explicit HTTP(S) origins")
        return value
