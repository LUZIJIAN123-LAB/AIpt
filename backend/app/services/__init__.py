"""Business services — async SQLAlchemy against real PostgreSQL tables.

All functions are async and manage their own AsyncSession via
``AsyncSessionLocal`` from ``app.db.session``. Router callers only need
to ``await`` them — no need to pass ``db`` explicitly.

MemoryDocumentStore / MemoryConversationStore are kept for reference
but no longer used by these functions.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.models import Chunk, Conversation, Document, Message
from app.db.session import AsyncSessionLocal
from app.schemas import ConversationCreate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _get_session() -> AsyncSession:
    """Context-managed session — use via ``async with _get_session() as db``."""
    return AsyncSessionLocal()


# ===============================================================
# Documents
# ===============================================================

def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_upload_to_temp(file_bytes: bytes, filename: str) -> Path:
    """Persist an upload into a per-session temp file — caller handles cleanup."""
    tmp_dir = Path(tempfile.gettempdir()) / "aipt_uploads"
    tmp_dir.mkdir(exist_ok=True)
    target = tmp_dir / f"{uuid4().hex}_{Path(filename).name}"
    target.write_bytes(file_bytes)
    return target


async def ingest_upload(
    file_path: Path,
    filename: str,
    title: str | None = None,
) -> dict:
    """Upload pipeline: save → parse → chunk → embed → write Document + Chunks.

    Dedup by file_hash (unique constraint + explicit SELECT first so we can
    return a clean "skipped" response).
    """
    from app.llm import get_embedding_client
    from app.rag.chunker import chunk_document
    from app.services.parser import detect_file_type, parse_document

    file_hash = _file_hash(file_path)
    file_size = file_path.stat().st_size
    file_type = detect_file_type(filename)

    async with AsyncSessionLocal() as db:
        # --- Dedup ---
        existing = (await db.execute(
            select(Document).where(Document.file_hash == file_hash)
        )).scalar_one_or_none()
        if existing is not None:
            return {
                "document_id": str(existing.id),
                "skipped": True,
                "reason": "duplicate",
            }

        # --- Parse + Chunk (sync) ---
        parsed = parse_document(file_path)
        chunks_info = chunk_document(
            parsed,
            chunk_size=settings.RAG_CHUNK_SIZE,
            overlap=settings.RAG_CHUNK_OVERLAP,
        )
        if not chunks_info:
            raise ValueError("Document produced zero chunks")

        # --- Embed (sync) ---
        emb = get_embedding_client()
        texts = [c.content for c in chunks_info]
        embeddings = emb.embed_batch(texts)
        pad = emb.dimension if hasattr(emb, "dimension") else settings.EMBEDDING_DIM
        embeddings = embeddings + [[0.0] * pad] * (len(chunks_info) - len(embeddings))

        # --- Persist Document ---
        # Copy uploaded file to permanent storage before writing its path to DB,
        # so tempfile cleanup in upload route doesn't orphan the record.
        import shutil
        storage_root = Path(settings.APP_STORAGE_DIR)
        storage_root.mkdir(parents=True, exist_ok=True)
        permanent_path = storage_root / f"{file_hash}{file_path.suffix}"
        try:
            if not permanent_path.exists():
                shutil.copy2(file_path, permanent_path)
        except OSError:
            # Non-fatal — storage_path may still be useful for debugging;
            # upload flow itself succeeded (parse + chunk + embed all done).
            permanent_path = file_path

        doc = Document(
            id=uuid4(),
            filename=filename,
            file_type=file_type,
            storage_path=str(permanent_path),
            file_size=file_size,
            file_hash=file_hash,
            parse_status="done",
            title=title,
        )
        db.add(doc)

        # --- Persist Chunks ---
        embed_model = getattr(emb, "model", settings.EMBEDDING_MODEL)
        chunk_rows = [
            Chunk(
                id=uuid4(),
                document_id=doc.id,
                chunk_index=c.index,
                content=c.content,
                chunk_type=c.chunk_type,
                start_offset=c.start_offset,
                end_offset=c.end_offset,
                embedding=embeddings[i],
                embed_model=embed_model,
                embed_status="done",
            )
            for i, c in enumerate(chunks_info)
        ]
        db.add_all(chunk_rows)
        await db.commit()

    return {
        "document_id": str(doc.id),
        "chunk_count": len(chunks_info),
        "word_count": parsed.word_count,
        "file_type": file_type,
        "skipped": False,
        "title": title,
    }


async def list_documents(
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    async with AsyncSessionLocal() as db:
        # --- Total ---
        total = (await db.execute(
            select(func.count(Document.id))
        )).scalar_one() or 0

        # --- Paginated docs ---
        docs = (await db.execute(
            select(Document)
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()

        items: list[dict] = []
        for d in docs:
            chunk_count = (await db.execute(
                select(func.count(Chunk.id)).where(Chunk.document_id == d.id)
            )).scalar_one() or 0
            items.append({
                "id": str(d.id),
                "filename": d.filename,
                "file_type": d.file_type,
                "parse_status": d.parse_status,
                "chunk_count": chunk_count,
                "title": d.title,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            })

    return items, total


async def get_document(doc_id: UUID) -> dict:
    async with AsyncSessionLocal() as db:
        doc = (await db.execute(
            select(Document).where(Document.id == doc_id)
        )).scalar_one_or_none()
        if doc is None:
            raise NotFoundError(message=f"Document {doc_id} not found")

        chunks = (await db.execute(
            select(Chunk)
            .where(Chunk.document_id == doc_id)
            .order_by(Chunk.chunk_index)
        )).scalars().all()

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_type": doc.file_type,
        "parse_status": doc.parse_status,
        "chunk_count": len(chunks),
        "word_count": sum(len(c.content.split()) for c in chunks),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "chunks": [
            {
                "index": c.chunk_index,
                "content": c.content,
                "chunk_type": c.chunk_type,
                "start_offset": c.start_offset,
                "end_offset": c.end_offset,
            }
            for c in chunks
        ],
    }


async def delete_document(doc_id: UUID) -> bool:
    async with AsyncSessionLocal() as db:
        doc = (await db.execute(
            select(Document).where(Document.id == doc_id)
        )).scalar_one_or_none()
        if doc is None:
            raise NotFoundError(message=f"Document {doc_id} not found")
        await db.delete(doc)  # cascade="all, delete-orphan" takes chunks with it
        await db.commit()
    return True


# ===============================================================
# Conversations
# ===============================================================

async def create_conversation(body: ConversationCreate) -> dict:
    async with AsyncSessionLocal() as db:
        conv = Conversation(
            id=uuid4(),
            title=body.title or "新对话",
            created_by=body.created_by,
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

    return {
        "id": str(conv.id),
        "title": conv.title,
        "created_by": conv.created_by,
        "message_count": 0,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


async def list_conversations(
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    async with AsyncSessionLocal() as db:
        # Only conversations that have at least one message — otherwise an
        # accidental "create but never asked anything" pollutes the sidebar.
        total = (await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.id.in_(
                    select(Message.conversation_id).distinct()
                )
            )
        )).scalar_one() or 0

        convs = (await db.execute(
            select(Conversation)
            .where(Conversation.id.in_(
                select(Message.conversation_id).distinct()
            ))
            .order_by(Conversation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()

        out: list[dict] = []
        for c in convs:
            msg_count = (await db.execute(
                select(func.count(Message.id)).where(Message.conversation_id == c.id)
            )).scalar_one() or 0
            out.append({
                "id": str(c.id),
                "title": c.title,
                "created_by": c.created_by,
                "message_count": msg_count,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            })

    return out, total


async def get_conversation(conv_id: UUID) -> dict:
    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()
        if conv is None:
            raise NotFoundError(message=f"Conversation {conv_id} not found")

        messages = (await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
        )).scalars().all()

    return {
        "id": str(conv.id),
        "title": conv.title,
        "created_by": conv.created_by,
        "message_count": len(messages),
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "rag_sources": m.rag_sources,
                "rewritten_query": m.rewritten_query,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


async def delete_conversation(conv_id: UUID) -> bool:
    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()
        if conv is None:
            raise NotFoundError(message=f"Conversation {conv_id} not found")
        await db.delete(conv)  # cascade="all, delete-orphan"
        await db.commit()
    return True


# ===============================================================
# Ask / Search — hybrid retrieval from real DB
# ===============================================================

async def do_search(
    query: str,
    top_k: int | None = None,
    document_id: UUID | None = None,
) -> tuple[list, float]:
    """Hybrid search — fetch chunks + embeddings from DB, then run
    Python-side BM25 + vector cosine + rerank (pgvector extension-free)."""
    from app.llm import get_embedding_client
    from app.rag.retriever import build_hybrid_index, hybrid_search

    k = top_k or settings.RAG_FINAL_TOP_K
    t0 = time.perf_counter()

    async with AsyncSessionLocal() as db:
        stmt = select(Chunk)
        if document_id is not None:
            stmt = stmt.where(Chunk.document_id == document_id)
        chunks = (await db.execute(stmt)).scalars().all()

    if not chunks:
        return [], (time.perf_counter() - t0) * 1000

    # Build hybrid index from DB rows
    chunks_text = [c.content for c in chunks]
    embeddings: list[list[float]] = []
    for c in chunks:
        if c.embedding and all(v is not None for v in c.embedding):
            embeddings.append([float(v) for v in c.embedding])
        else:
            embeddings.append([0.0] * settings.EMBEDDING_DIM)

    h = build_hybrid_index(
        chunks_text,
        embeddings,
        k_vector=settings.RAG_VECTOR_TOP_K,
        k_bm25=settings.RAG_BM25_TOP_K,
        k_final=k,
        alpha=settings.RAG_HYBRID_ALPHA,
        beta=settings.RAG_HYBRID_BETA,
    )

    emb = get_embedding_client()
    query_vec = emb.embed(query)

    results = hybrid_search(h, query, query_vec)

    # Resolve document filename per chunk
    doc_ids = list({chunks[r.index].document_id for r in results})
    doc_map: dict[UUID, str] = {}
    if doc_ids:
        async with AsyncSessionLocal() as db:
            docs = (await db.execute(
                select(Document.id, Document.filename).where(Document.id.in_(doc_ids))
            )).all()
            doc_map = {row[0]: row[1] for row in docs}

    items = []
    for r in results:
        c = chunks[r.index]
        items.append({
            "content": r.content,
            "document_id": str(c.document_id),
            "document_filename": doc_map.get(c.document_id, ""),
            "chunk_index": c.chunk_index,
            "vector_score": round(r.vector_score, 4),
            "bm25_score": round(r.bm25_score, 4),
            "final_score": round(r.final_score, 4),
            "source": r.source,
        })

    return items, (time.perf_counter() - t0) * 1000


# ===============================================================
# Multi-turn context rewrite + message persistence
# ===============================================================

async def rewrite_query(conv_id: UUID, current_query: str) -> str:
    """Use LLM to convert a potentially referential query into a self-contained
    question using conversation history. Falls back to ``current_query``."""
    from app.llm import get_llm_client
    from app.llm.base import ChatMessage

    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()
        if conv is None:
            return current_query

        messages = (await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc())
            .limit(6)
        )).scalars().all()

    if not messages:
        return current_query

    history_lines: list[str] = []
    for m in reversed(messages):  # re-chronological for prompt
        role_label = "用户" if m.role == "user" else "助手"
        history_lines.append(f"{role_label}: {m.content}")
    history_str = "\n".join(history_lines)

    prompt = (
        "你是一个多轮对话改写器。请基于以下对话历史，把用户当前问题改写成一个"
        "**完整独立**的问题，消除所有指代（它、这个、那个、上面、之前等）。\n\n"
        f"--- 对话历史 ---\n{history_str}\n\n"
        f"--- 用户当前问题 ---\n{current_query}\n\n"
        "--- 改写后问题（只输出改写结果，不要解释） ---"
    )

    llm = get_llm_client()
    try:
        resp = llm.chat([ChatMessage(role="user", content=prompt)], temperature=0.0)
        rewritten = resp.content.strip()
        _BAD_HINTS = ("Mock", "资料问答助手", "改写器", "对话历史")
        if (len(rewritten) < 2
                or any(h in rewritten for h in _BAD_HINTS)
                or len(rewritten) > 300):
            return current_query
        return rewritten
    except Exception:
        return current_query


async def persist_ask_messages(
    conv_id: UUID,
    *,
    query: str,
    rewritten_query: str | None,
    answer: str,
    rag_sources: list[dict] | None = None,
) -> None:
    """Store user + assistant messages for a /ask call.

    Also: first-ever message auto-promotes the conversation title from the
    default placeholder to a truncated copy of the user's first question.
    """
    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()

        # Auto-title on first message — 40-char truncate, no leading/trailing whitespace.
        if conv is not None and (not conv.title or conv.title in ("新对话", "New Conversation")):
            trimmed = query.strip().replace("\n", " ")
            if len(trimmed) > 40:
                trimmed = trimmed[:40].rstrip() + "…"
            conv.title = trimmed or "新对话"
            db.add(conv)

        db.add_all([
            Message(
                id=uuid4(),
                conversation_id=conv_id,
                role="user",
                content=query,
                rewritten_query=rewritten_query,
            ),
            Message(
                id=uuid4(),
                conversation_id=conv_id,
                role="assistant",
                content=answer,
                rag_sources=rag_sources,
            ),
        ])
        await db.commit()
