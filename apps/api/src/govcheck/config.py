from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str | None = None
    llm_provider: Literal["fake", "ollama", "groq"] = "fake"
    groq_api_key: SecretStr | None = Field(default=None, repr=False)
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"
    embedding_provider: Literal["fake", "sentence-transformer"] = "fake"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dimension: int = 384
    max_upload_bytes: int = 5_242_880
    max_pdf_pages: int = 50
    retention_minutes: int = 60
    analysis_job_timeout_minutes: int = Field(default=10, ge=5, le=60)
    rate_limit_requests: int = Field(default=120, ge=1, le=10_000)
    rate_limit_client_requests: int = Field(default=600, ge=1, le=100_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    rate_limit_max_keys: int = Field(default=10_000, ge=100, le=100_000)
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @model_validator(mode="after")
    def validate_production_database(self) -> "Settings":
        if self.environment == "production" and not self.database_url:
            raise ValueError("DATABASE_URL is required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
