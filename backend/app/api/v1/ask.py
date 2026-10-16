"""Ask endpoint — the RAG star.

POST /api/v1/ask   -> SSE  stream (default)
                     or plain 200 JSON if stream=false

Protocol (SSE):
    event: start        (query, top_k, source_count, rewritten_query if multi-turn)
    event: rewrite      (rewritten_query — when context rewrite happened)
    event: source       (one per retrieved chunk — frontend uses these for 来源引用高亮)
    event: generating   (streaming delta chunks from the LLM)
    event: usage        (final usage stats)
    event: done         (stream closed)
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.responses import SuccessResponse
from app.llm import get_llm_client
from app.llm.base import ChatMessage
from app.rag.pipeline import build_rag_prompt
from app.schemas import AskRequest
from app.services import do_search, persist_ask_messages, rewrite_query

router = APIRouter(prefix="/ask")


# --- SSE helpers ---

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",   # disables Nginx buffering so first byte arrives fast
    "Content-Type": "text/event-stream; charset=utf-8",
}


def _sse(event: str, data: Any) -> str:
    """Serialize one SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# --- Endpoints ---

@router.post("", summary="RAG answer (SSE stream by default)", response_model=None)
async def ask(body: AskRequest) -> StreamingResponse | dict:
    if body.stream:
        return StreamingResponse(_stream_answer(body), headers=_SSE_HEADERS)
    return SuccessResponse(data=await _plain_answer(body)).model_dump()


@router.post("/rewrite", summary="Standalone multi-turn context rewrite")
async def rewrite(body: AskRequest) -> dict:
    """Rewrite a referential query using conversation history."""
    if body.conversation_id is None:
        return SuccessResponse(data={"rewritten_query": body.query, "used_history": False}).model_dump()

    rewritten = await rewrite_query(body.conversation_id, body.query)
    used = rewritten != body.query
    return SuccessResponse(data={
        "rewritten_query": rewritten,
        "used_history": used,
        "conversation_id": str(body.conversation_id),
    }).model_dump()


# --- internals ---

async def _maybe_rewrite(query: str, conv_id: UUID | None) -> tuple[str, str | None]:
    """Return (effective_query, rewritten_query_or_None)."""
    if conv_id is None:
        return query, None
    rewritten = await rewrite_query(conv_id, query)
    if rewritten == query:
        return query, None  # no change — either no history or LLM kept it
    return rewritten, rewritten


async def _plain_answer(body: AskRequest) -> dict:
    """Non-stream path — assemble prompt -> LLM.chat -> persist."""
    effective_query, rewritten = await _maybe_rewrite(body.query, body.conversation_id)
    items, lat_ms = await do_search(effective_query, top_k=body.top_k)
    llm = get_llm_client()

    if not items:
        answer_text = "知识库中没有找到相关资料，请先上传文档后再试。"
        sources = []
    else:
        prompt = build_rag_prompt(effective_query, _to_retrieved_chunks(items))
        msg = ChatMessage(role="user", content=prompt)
        resp = llm.chat([msg], temperature=0.3)
        answer_text = resp.content
        sources = items

    if body.conversation_id is not None:
        await persist_ask_messages(
            body.conversation_id,
            query=body.query, rewritten_query=rewritten,
            answer=answer_text, rag_sources=sources,
        )

    return {
        "answer": answer_text,
        "query_used": effective_query,
        "rewritten_query": rewritten,
        "rag_sources": sources,
        "latency_ms": round(lat_ms, 2),
    }


async def _stream_answer(body: AskRequest) -> AsyncIterator[str]:
    """SSE generator — rewrite → retrieve → stream → persist on done."""
    t0 = time.perf_counter()

    # 0) multi-turn rewrite (if conversation_id provided)
    effective_query, rewritten = await _maybe_rewrite(body.query, body.conversation_id)

    # 1) start event (before any blocking work — helps frontend render "loading")
    yield _sse("start", {
        "query": body.query,
        "query_used": effective_query,
        "top_k": body.top_k or settings.RAG_FINAL_TOP_K,
    })
    if rewritten is not None:
        yield _sse("rewrite", {"rewritten_query": rewritten})

    # 2) hybrid retrieval
    items, search_ms = await do_search(effective_query, top_k=body.top_k)

    yield _sse("start", {  # second start carries retrieval metadata
        "source_count": len(items),
        "top_k": body.top_k or settings.RAG_FINAL_TOP_K,
    })

    # 3) source events — frontend "来源引用高亮"
    for s in items:
        yield _sse("source", {
            "content": s["content"],
            "document_id": s["document_id"],
            "document_filename": s["document_filename"],
            "chunk_index": s["chunk_index"],
            "final_score": s["final_score"],
            "source": s["source"],
        })

    # 4) generation + buffer answer for persistence
    llm = get_llm_client()
    t_first_token_ms: float | None = None
    answer_buf: list[str] = []

    if not items:
        fallback_text = "知识库中没有找到相关资料，请先上传文档后再试。"
        async for chunk in _fallback_stream(fallback_text):
            yield chunk
        answer_text = fallback_text
    else:
        prompt = build_rag_prompt(effective_query, _to_retrieved_chunks(items))
        msg = ChatMessage(role="user", content=prompt)
        try:
            async for c in llm.chat([msg], stream=True, temperature=0.3):
                if c.type == "delta":
                    if t_first_token_ms is None:
                        t_first_token_ms = (time.perf_counter() - t0) * 1000
                    answer_buf.append(c.content)
                    yield _sse("generating", {"content": c.content})
                elif c.type == "usage":
                    yield _sse("usage", {
                        "prompt_tokens": c.usage_prompt,
                        "completion_tokens": c.usage_completion,
                    })
        except Exception as e:
            err_text = f"[生成异常: {e}]"
            answer_buf.append(err_text)
            yield _sse("generating", {"content": err_text})

        answer_text = "".join(answer_buf)

    # 5) persist messages (after stream completes — we have the full answer now)
    if body.conversation_id is not None:
        await persist_ask_messages(
            body.conversation_id,
            query=body.query, rewritten_query=rewritten,
            answer=answer_text, rag_sources=items if items else None,
        )

    # 6) done
    t_end = time.perf_counter()
    yield _sse("done", {
        "first_token_ms": round(t_first_token_ms, 2) if t_first_token_ms else None,
        "total_ms": round((t_end - t0) * 1000, 2),
        "retrieval_ms": round(search_ms, 2),
        "provider": getattr(llm, "provider", "unknown"),
        "query_used": effective_query,
    })


async def _fallback_stream(text: str) -> AsyncIterator[str]:
    """Char-by-char SSE when no sources are retrieved — keeps the UI flow consistent."""
    for ch in text:
        await asyncio.sleep(0.005)
        yield _sse("generating", {"content": ch})


def _to_retrieved_chunks(items: list[dict]):
    """Convert dict search results back to RetrievedChunk for build_rag_prompt."""
    from app.rag.retriever import RetrievedChunk
    return [
        RetrievedChunk(
            index=it["chunk_index"],
            content=it["content"],
            vector_score=it["vector_score"],
            bm25_score=it["bm25_score"],
            final_score=it["final_score"],
            source=it["source"],
        )
        for it in items
    ]
