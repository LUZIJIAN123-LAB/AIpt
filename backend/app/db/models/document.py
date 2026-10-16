"""Document table — one row per uploaded file."""
from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.chunk import Chunk


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    # --- Identity ---
    filename: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="pdf | docx | md | txt"
    )

    # --- Storage ---
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # --- Parsing state ---
    # pending | parsing | done | error
    parse_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Optional metadata ---
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tags: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Comma-separated tags"
    )

    # --- Relationships ---
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
