"""Typed application settings loaded from environment variables.

All downstream modules import the singleton `settings` instance.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """General FastAPI application settings."""

    APP_NAME: str = "AIpt RAG Platform"
    APP_ENV: Literal["dev", "prod"] = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    # Where uploaded files are kept permanently (relative to backend working dir).
    APP_STORAGE_DIR: str = "data/uploads"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.APP_CORS_ORIGINS.split(",") if o.strip()]


class PostgresSettings(BaseSettings):
    """PostgreSQL connection. pgvector extension is required on the DB."""

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "aipt"
    POSTGRES_PASSWORD: str = "aipt"
    POSTGRES_DB: str = "aipt"

    @property
    def dsn(self) -> str:
        """asyncpg DSN for SQLAlchemy create_async_engine."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


class RedisSettings(BaseSettings):
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


class LLMProviderSettings(BaseSettings):
    """Single LLM provider config (both primary and fallback reuse this shape)."""

    LLM_PROVIDER: Literal["deepseek", "glm", "qwen"] = "deepseek"
    LLM_API_KEY: str = Field(default="", description="API key for this provider")
    LLM_BASE_URL: str = Field(default="", description="OpenAI-compatible base URL")
    LLM_MODEL: str = Field(default="", description="Model id")

    LLM_FALLBACK_PROVIDER: Literal["deepseek", "glm", "qwen"] = "qwen"
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_BASE_URL: str = ""
    LLM_FALLBACK_MODEL: str = ""


class EmbeddingSettings(BaseSettings):
    EMBEDDING_PROVIDER: Literal["deepseek", "glm", "qwen"] = "qwen"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIM: int = 1024


class RAGSettings(BaseSettings):
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 100
    RAG_VECTOR_TOP_K: int = 10
    RAG_BM25_TOP_K: int = 10
    RAG_FINAL_TOP_K: int = 6
    RAG_HYBRID_ALPHA: float = 0.6   # weight on vector score in rerank
    RAG_HYBRID_BETA: float = 0.4    # weight on BM25 score in rerank


class AuthSettings(BaseSettings):
    """JWT auth — use a long random string for JWT_SECRET in production."""
    AUTH_JWT_SECRET: str = "aipt-dev-secret-change-me-in-prod-000000"
    AUTH_JWT_ALGO: Literal["HS256", "HS384", "HS512"] = "HS256"
    AUTH_JWT_EXPIRE_MINUTES: int = 60 * 12  # 12 hours


class Settings(
    AppSettings,
    PostgresSettings,
    RedisSettings,
    LLMProviderSettings,
    EmbeddingSettings,
    RAGSettings,
    AuthSettings,
):
    """Aggregated settings — all env vars live in one flat namespace."""

    # Only load .env — never load .env.example as a live env file,
    # because pydantic-settings applies files left-to-right *overwriting*
    # each other and example's empty strings would clobber real secrets.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor — import `from app.core.config import settings`."""
    return Settings()


settings = get_settings()
