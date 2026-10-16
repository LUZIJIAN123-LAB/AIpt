"""OpenAI-compatible provider client — works for DeepSeek, GLM, Qwen, and any other
provider that exposes the Chat Completions + Embeddings endpoint shapes.

Real HTTP calls are guarded by settings. For local dev without API keys, factory.py
returns the Mock client instead, so this file is only hit in production-like configs.

Retry logic uses tenacity (retry=3, wait=1s, exponential backoff, reraise LLMError).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import LLMError, EmbeddingError
from app.llm.base import (
    BaseEmbeddingClient,
    BaseLLMClient,
    ChatMessage,
    ChatResponse,
    StreamChunk,
)

# SSE delimiter — matches OpenAI and all compatible providers.
_SSE_DATA_PREFIX = "data: "
_SSE_DONE = "[DONE]"


class OpenAICompatLLMClient(BaseLLMClient):
    """Chat completion (sync and streaming) via /v1/chat/completions."""

    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self._api_key = api_key
        # Normalize base_url — OpenAI-compatible usually expects the /v1 already appended.
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # --- non-streaming ---

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self._timeout, headers=self._headers) as client:
                r = client.post(url, json=payload)
        except httpx.HTTPError as e:
            raise LLMError(
                message=f"{self.provider} chat request failed: {e}",
                detail=str(e),
            ) from e

        if r.status_code >= 400:
            raise LLMError(
                message=f"{self.provider} chat {r.status_code}",
                detail=r.text[:500],
            )
        return r.json()

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
            return self._chat_stream(messages, temperature, max_tokens, extra)

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if extra:
            payload.update(extra)

        try:
            data = self._post_chat(payload)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(message=f"{self.provider} chat parse failed: {e}", detail=str(e)) from e

        choice = (data.get("choices") or [{}])[0]
        msg = (choice.get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return ChatResponse(
            content=msg,
            usage_prompt=usage.get("prompt_tokens", 0),
            usage_completion=usage.get("completion_tokens", 0),
            model=data.get("model", self.model),
        )

    # --- streaming (SSE) ---

    async def _chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
        extra: dict[str, Any] | None,
    ) -> AsyncIterator[StreamChunk]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if extra:
            payload.update(extra)

        url = f"{self._base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=self._headers
            ) as client:
                async with client.stream("POST", url, json=payload) as r:
                    if r.status_code >= 400:
                        body = await r.aread()
                        raise LLMError(
                            message=f"{self.provider} chat_stream {r.status_code}",
                            detail=body.decode()[:500],
                        )
                    async for raw_line in r.aiter_lines():
                        line = raw_line.strip()
                        if not line or not line.startswith(_SSE_DATA_PREFIX):
                            continue
                        data = line[len(_SSE_DATA_PREFIX):]
                        if data == _SSE_DONE:
                            yield StreamChunk(type="done")
                            break
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choice = (obj.get("choices") or [{}])[0]
                        delta = choice.get("delta") or {}
                        content = delta.get("content") or ""
                        usage = obj.get("usage")
                        if usage:
                            yield StreamChunk(
                                type="usage",
                                usage_prompt=usage.get("prompt_tokens", 0),
                                usage_completion=usage.get("completion_tokens", 0),
                            )
                        elif content:
                            yield StreamChunk(type="delta", content=content)
        except LLMError:
            raise
        except httpx.HTTPError as e:
            raise LLMError(message=f"{self.provider} stream failed: {e}", detail=str(e)) from e


class FallbackLLMClient(BaseLLMClient):
    """Tries primary → on LLMError → tries fallback. Tenacity is still applied on each."""

    provider = "fallback"
    model = ""

    def __init__(self, *, primary: OpenAICompatLLMClient, fallback: OpenAICompatLLMClient) -> None:
        self._primary = primary
        self._fallback = fallback
        self.provider = f"{primary.provider}|{fallback.provider}"

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> ChatResponse | AsyncIterator[StreamChunk]:
        try:
            return self._primary.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                extra=extra,
            )
        except LLMError as primary_err:
            logger.warning(
                f"[LLM] primary {self._primary.provider} failed, falling back to {self._fallback.provider}: {primary_err}"
            )
            return self._fallback.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                extra=extra,
            )


# --- Embedding ---

class OpenAICompatEmbeddingClient(BaseEmbeddingClient):
    """POST /v1/embeddings — returns list of floats per input."""

    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        dimension: int,
        timeout: float = 30.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.dimension = dimension
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    def _post_embeddings(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/embeddings"
        try:
            with httpx.Client(timeout=self._timeout, headers=self._headers) as client:
                r = client.post(url, json=payload)
        except httpx.HTTPError as e:
            raise EmbeddingError(
                message=f"{self.provider} embed request failed: {e}",
                detail=str(e),
            ) from e
        if r.status_code >= 400:
            raise EmbeddingError(
                message=f"{self.provider} embed {r.status_code}",
                detail=r.text[:500],
            )
        return r.json()

    def embed(self, text: str) -> list[float]:
        vectors = self.embed_batch([text])
        return vectors[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": self.model, "input": texts, "dimensions": self.dimension}
        try:
            data = self._post_embeddings(payload)
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(
                message=f"{self.provider} embed parse failed: {e}",
                detail=str(e),
            ) from e

        result = []
        for item in data.get("data", []):
            vec = item.get("embedding") or []
            if isinstance(vec, list) and vec:
                result.append([float(v) for v in vec])
        return result
