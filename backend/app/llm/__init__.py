"""Unified LLM client abstraction.

Usage:
    from app.llm import get_llm_client, get_embedding_client
    llm = get_llm_client()        # picks provider from settings, with fallback
    emb = get_embedding_client()

For local development (no API keys), set APP_ENV=dev and no providers
configured -> MockLLMClient / MockEmbeddingClient are auto-selected.
"""
from __future__ import annotations

from app.core.config import settings
from app.llm.base import BaseEmbeddingClient, BaseLLMClient
from app.llm.factory import build_llm_client, build_embedding_client


_llm_client: BaseLLMClient | None = None
_embedding_client: BaseEmbeddingClient | None = None


def get_llm_client() -> BaseLLMClient:
    """Singleton — picks real or mock based on settings."""
    global _llm_client
    if _llm_client is None:
        _llm_client = build_llm_client(settings)
    return _llm_client


def get_embedding_client() -> BaseEmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = build_embedding_client(settings)
    return _embedding_client


def reset_clients() -> None:
    """Primarily for tests — rebuild on next access."""
    global _llm_client, _embedding_client
    _llm_client = None
    _embedding_client = None


__all__ = [
    "BaseLLMClient",
    "BaseEmbeddingClient",
    "get_llm_client",
    "get_embedding_client",
    "reset_clients",
]
