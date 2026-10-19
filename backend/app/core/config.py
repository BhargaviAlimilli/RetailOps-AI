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
    ai_provider: Literal["disabled", "gemini"] = "disabled"
    ai_model: str | None = Field(
        default=None, min_length=1, max_length=120, pattern=r"^(models/)?gemini-[a-z0-9._-]+$"
    )
    gemini_api_key: SecretStr | None = None
    ai_timeout_seconds: float = Field(default=45, gt=0, le=120)
    ai_max_output_tokens: int = Field(default=1024, ge=64, le=4096)
    ai_max_retries: int = Field(default=1, ge=0, le=2)
    ai_max_active_per_user: int = Field(default=2, ge=1, le=4)
    ai_max_active_global: int = Field(default=4, ge=1, le=16)
    ai_max_generations_per_minute: int = Field(default=10, ge=1, le=60)
    ai_max_generations_per_day: int = Field(default=100, ge=1, le=1000)
    ai_max_conversations_per_user: int = Field(default=100, ge=1, le=100)
    rag_enabled: bool = False
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", pattern=r"^gemini-embedding-[a-z0-9._-]+$"
    )
    rag_embedding_dimensions: int = Field(default=768, ge=768, le=768)
    rag_max_document_characters: int = Field(default=100000, ge=1000, le=100000)
    rag_max_documents_per_user: int = Field(default=50, ge=1, le=50)
    rag_max_chunks_per_document: int = Field(default=200, ge=1, le=200)
    rag_embedding_batch_size: int = Field(default=16, ge=1, le=16)
    rag_timeout_seconds: float = Field(default=30, gt=0, le=60)
    rag_max_query_characters: int = Field(default=2000, ge=1, le=8000)
    rag_max_queries_per_minute: int = Field(default=20, ge=1, le=60)
    rag_max_queries_per_day: int = Field(default=200, ge=1, le=1000)
    rag_max_ingestions_per_day: int = Field(default=20, ge=1, le=50)
    rag_semantic_max_distance: float = Field(default=0.5, ge=0, le=1)
    rag_rerank_enabled: bool = True

    @field_validator("ai_model", mode="before")
    @classmethod
    def strip_model_identifier(cls, value):
        return value.strip() if isinstance(value, str) else value

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
