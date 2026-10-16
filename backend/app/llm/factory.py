"""Provider factory — reads Settings, returns the right client (or Mock).

Selection rules (both LLM and Embedding share this logic):
    1. If provider is set + API key is non-empty *and* not a placeholder → real client
    2. Else                                                            → Mock client

Placeholder keys (sk-xxx / your_key_here / etc.) are treated as missing, which lets
`.env.example` ship with template values without accidentally selecting real clients.
"""
from __future__ import annotations

import re

from app.core.config import Settings
from app.llm.base import BaseEmbeddingClient, BaseLLMClient


_PLACEHOLDER_RE = re.compile(r"^(sk-xxx|sk-yyy|sk-[a-z_]+$|your[_-]?key|xxx|yyy|changeme)", re.I)


def _has_real_key(key: str | None) -> bool:
    if not key or not key.strip():
        return False
    return not _PLACEHOLDER_RE.match(key.strip())


def build_llm_client(settings: Settings) -> BaseLLMClient:
    if _has_real_key(settings.LLM_API_KEY) and _has_real_key(settings.LLM_BASE_URL):
        from app.llm.openai_compat import OpenAICompatLLMClient

        primary = OpenAICompatLLMClient(
            provider=settings.LLM_PROVIDER,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
        )

        if _has_real_key(settings.LLM_FALLBACK_API_KEY) and _has_real_key(settings.LLM_FALLBACK_BASE_URL):
            fallback = OpenAICompatLLMClient(
                provider=settings.LLM_FALLBACK_PROVIDER,
                api_key=settings.LLM_FALLBACK_API_KEY,
                base_url=settings.LLM_FALLBACK_BASE_URL,
                model=settings.LLM_FALLBACK_MODEL,
            )
            from app.llm.openai_compat import FallbackLLMClient

            return FallbackLLMClient(primary=primary, fallback=fallback)

        return primary

    from app.llm.mock import MockLLMClient

    return MockLLMClient()


def build_embedding_client(settings: Settings) -> BaseEmbeddingClient:
    if _has_real_key(settings.EMBEDDING_API_KEY) and _has_real_key(settings.EMBEDDING_BASE_URL):
        from app.llm.openai_compat import OpenAICompatEmbeddingClient

        return OpenAICompatEmbeddingClient(
            provider=settings.EMBEDDING_PROVIDER,
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
            model=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIM,
        )

    from app.llm.mock import MockEmbeddingClient

    return MockEmbeddingClient(dimension=settings.EMBEDDING_DIM)
