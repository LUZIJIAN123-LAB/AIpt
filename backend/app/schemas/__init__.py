"""Pydantic request/response models — single source of truth for all API shapes.

FastAPI generates OpenAPI docs directly from these models.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# -------- common --------

class AppResponse(BaseModel):
    """Generic envelope — mirrors app.core.responses.SuccessResponse."""
    model_config = ConfigDict(extra="forbid")
    code: Literal["OK"] = "OK"
    message: str = "success"
    data: Any = None


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    detail: Any = None


# -------- document --------

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    parse_status: str
    title: str | None = None
    tags: str | None = None
    chunk_count: int = 0
    word_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int = 1
    page_size: int = 20


class DocumentChunkItem(BaseModel):
    index: int
    content: str
    chunk_type: str
    start_offset: int | None = None
    end_offset: int | None = None


class DocumentDetailResponse(DocumentResponse):
    chunks: list[DocumentChunkItem] = Field(default_factory=list)


# -------- search --------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    top_k: int | None = Field(default=None, description="Defaults to RAG_FINAL_TOP_K")
    document_id: UUID | None = Field(default=None, description="Restrict search to one doc")


class SearchChunkResponse(BaseModel):
    content: str
    document_id: UUID
    document_filename: str
    chunk_index: int
    vector_score: float = 0.0
    bm25_score: float = 0.0
    final_score: float = 0.0
    source: str = ""


class SearchResponse(BaseModel):
    query: str
    chunks: list[SearchChunkResponse]
    latency_ms: float = 0.0


# -------- conversation --------

class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    created_by: str | None = Field(default=None, max_length=128)


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_by: str | None
    message_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int
    page: int = 1
    page_size: int = 20


class MessageResponse(BaseModel):
    id: UUID
    role: Literal["system", "user", "assistant"]
    content: str
    rag_sources: list[dict[str, Any]] | None = None
    rewritten_query: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = Field(default_factory=list)


# -------- ask --------

class AskRequest(BaseModel):
    """The SSE endpoint uses this body — conversation_id can be omitted for ad-hoc RAG."""
    query: str = Field(..., min_length=1, max_length=500)
    conversation_id: UUID | None = None
    top_k: int | None = None
    stream: bool = True


class AskRewriteRequest(BaseModel):
    """Standalone context rewrite (used by some clients before search)."""
    query: str = Field(..., min_length=1, max_length=500)
    conversation_id: UUID
