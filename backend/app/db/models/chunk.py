"""Chunk table — one row per text chunk with a PostgreSQL ARRAY(Float) embedding."""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.document import Document


class Chunk(IdMixin, TimestampMixin, Base):
    __tablename__ = "chunks"

    # --- Link to source ---
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Chunk identity within a document ---
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chunk_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="text", comment="text | heading | code"
    )

    # --- Content ---
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Character-level offset inside the document — for "click to jump".
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Embedding ---
    # Native PostgreSQL float[] — no pgvector extension required.
    # Python side: list[float] or None.
    embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float), nullable=True
    )
    embed_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embed_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )

    # --- Relationships ---
    document: Mapped[Document] = relationship(back_populates="chunks")
