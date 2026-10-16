"""Mock LLM + Embedding clients — deterministic, offline, no API keys needed.

Used automatically when providers are not configured or APP_ENV=dev.

Embeddings: deterministic pseudo-random vectors derived from SHA-256 of the input text.
            Same text -> same vector, different text -> different vector.
            This lets us verify cosine-similarity retrieval logic end-to-end.

Chats:      Generic template reply — just enough to exercise the RAG pipeline.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import random
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from app.llm.base import (
    BaseEmbeddingClient,
    BaseLLMClient,
    ChatMessage,
    ChatResponse,
    StreamChunk,
)


# ---------------------------------------------------------------------------
# Helpers — deterministic pseudo-vector generation
# ---------------------------------------------------------------------------

def _text_to_seed(text: str) -> int:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def _make_vector(text: str, dim: int) -> list[float]:
    """Deterministic L2-normalized vector derived from text via SHA-256 + numpy."""
    rng = np.random.default_rng(_text_to_seed(text))
    vec = rng.standard_normal(dim)
    norm = float(np.linalg.norm(vec)) or 1.0
    return (vec / norm).tolist()


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class MockLLMClient(BaseLLMClient):
    """Offline mock — deterministic chat responses for local dev."""

    provider = "mock"
    model = "mock-chat"

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> ChatResponse | AsyncIterator[StreamChunk]:
        if stream:
            return self._chat_stream(messages)

        user_text = next((m.content for m in reversed(messages) if m.role == "user"), "")
        reply = self._format_reply(user_text)
        return ChatResponse(
            content=reply,
            usage_prompt=len("".join(m.content for m in messages)),
            usage_completion=len(reply),
            model=self.model,
        )

    async def _chat_stream(
        self, messages: list[ChatMessage]
    ) -> AsyncIterator[StreamChunk]:
        user_text = next((m.content for m in reversed(messages) if m.role == "user"), "")
        reply = self._format_reply(user_text)

        # Emit one chunk per word, with a tiny artificial delay so SSE timing code is exercised.
        words = reply.split(" ")
        for i, w in enumerate(words):
            piece = w + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.01)
            yield StreamChunk(type="delta", content=piece)

        yield StreamChunk(type="done")

    @staticmethod
    def _format_reply(user_text: str) -> str:
        """Heuristic reply — just returns a plausible response shape."""
        clean = user_text.strip()
        if not clean:
            return "Mock 收到空问题。请输入具体的知识问题以触发 RAG 检索。"

        # Look for context hint words that RAG would have retrieved.
        keywords = ["文档", "知识", "什么是", "怎么", "如何", "介绍", "细节"]
        matched = [k for k in keywords if k in clean]

        if "来源" in clean or "资料" in clean:
            return (
                f"关于「{clean[:40]}」，Mock RAG 系统已检索到相关片段。"
                f"（Step 4 验证用，真正的来源引用将在 Step 5+ 实现。）"
            )
        if matched:
            return (
                f"Mock 回答：您问的「{clean[:40]}」。"
                f"RAG 会先检索文档库中最相关的 Top-6 片段，"
                f"再基于这些片段生成答案。关键词匹配：{matched}。"
            )
        return (
            f"Mock RAG 回答：「{clean[:40]}」。"
            f"这是离线开发模式下的占位返回，"
            f"真实回答将在 Step 4 接入 LLM API 后启用。"
        )


# ---------------------------------------------------------------------------
# Mock Embedding
# ---------------------------------------------------------------------------

class MockEmbeddingClient(BaseEmbeddingClient):
    """Offline mock — deterministic vectors, same input -> same vector, L2-normalized."""

    provider = "mock"
    model = "mock-embedding"

    def __init__(self, dimension: int = 1024) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        return _make_vector(text, self.dimension)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [_make_vector(t, self.dimension) for t in texts]


# ---------------------------------------------------------------------------
# Test helper: verify cosine similarity logic on mock vectors
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine (handy for tests + sanity checks)."""
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)
