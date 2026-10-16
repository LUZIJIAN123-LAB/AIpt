"""Conversation + Message tables — multi-turn chat history."""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.message import Message


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    # --- Identity ---
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="新对话")

    # --- Optional scope (future: multi-tenant) ---
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # --- Relationships ---
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )


class Message(IdMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    # --- Link to conversation ---
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Role (OpenAI convention) ---
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="system | user | assistant"
    )

    # --- Content ---
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # --- RAG metadata on assistant replies ---
    # JSONB: [{chunk_id, score, snippet, document_id}, ...] or null for plain chat.
    rag_sources: Mapped[dict | list | None] = mapped_column(
        JSONB, nullable=True
    )
    # The rewritten query sent to retrieval (if any).
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
