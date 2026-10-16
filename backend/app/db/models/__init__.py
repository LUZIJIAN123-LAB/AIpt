"""Aggregate — import this module to register all models on Base.metadata."""
from __future__ import annotations

from app.db.base import Base

from app.db.models.document import Document
from app.db.models.chunk import Chunk
from app.db.models.conversation import Conversation, Message
from app.db.models.user import User

__all__ = ["Base", "Document", "Chunk", "Conversation", "Message", "User"]
