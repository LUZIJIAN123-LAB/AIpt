"""RAG helpers.

Only surviving function from the original pipeline.py — everything else
(MockChunkStore, ingest_document, answer, ...) was replaced by the real
SQLAlchemy + PostgreSQL implementation in app/services/__init__.py.
"""
from __future__ import annotations


def build_rag_prompt(query: str, chunks: list[object]) -> str:
    """Collapse retrieved chunks + query into a plain-text prompt string.

    Each chunk is expected to carry a `.content` attribute (e.g. RetrievedChunk
    from app.rag.retriever or the dict shape we pass from services.do_search).
    """
    context_parts: list[str] = []
    for i, c in enumerate(chunks):
        content = getattr(c, "content", None) or (
            c.get("content") if isinstance(c, dict) else str(c)
        )
        context_parts.append(f"[资料 {i + 1}]\n{content}")

    context_block = "\n\n".join(context_parts) if context_parts else "（无相关资料）"

    return (
        f"你是一个资料问答助手。请**仅基于以下提供的资料**回答用户问题，"
        f"不要使用外部知识，资料不足时明确说明。\n\n"
        f"--- 资料 ---\n{context_block}\n\n"
        f"--- 用户问题 ---\n{query}\n\n"
        f"--- 回答 ---"
    )
