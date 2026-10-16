"""Abstract base classes — every provider implements these methods."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

# --- Chat types ---

ChatRole = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    role: ChatRole
    content: str


@dataclass
class ChatResponse:
    """Non-streaming chat response."""
    content: str
    usage_prompt: int = 0
    usage_completion: int = 0
    model: str = ""


@dataclass
class StreamChunk:
    """One SSE-like chunk from a streaming response.

    type: 'delta'  — piece of assistant text (the common case)
          'usage'  — final usage info at end of stream
          'done'   — stream finished, no content
    """
    type: Literal["delta", "usage", "done"] = "delta"
    content: str = ""
    usage_prompt: int = 0
    usage_completion: int = 0


class BaseLLMClient(ABC):
    """Abstract chat client — sync-style interface, but returned from async FastAPI endpoints."""

    provider: str = "base"
    model: str = ""

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> ChatResponse | AsyncIterator[StreamChunk]:
        """Non-streaming returns ChatResponse; streaming returns AsyncIterator[StreamChunk]."""
        ...


# --- Embedding types ---

class BaseEmbeddingClient(ABC):
    """Abstract embedding client — always returns floats in the configured dimension."""

    provider: str = "base"
    model: str = ""
    dimension: int = 0

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Single text -> single embedding vector."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch of texts -> batch of vectors. Providers may have a per-call limit."""
        ...
