"""Hybrid search endpoint — retrieves ranked chunks without calling the LLM."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import SuccessResponse
from app.schemas import SearchRequest
from app.services import do_search

router = APIRouter(prefix="/search")


@router.post("", summary="Hybrid vector + BM25 search")
async def search(body: SearchRequest) -> dict:
    items, latency_ms = await do_search(
        body.query, top_k=body.top_k, document_id=body.document_id,
    )
    return SuccessResponse(data={
        "query": body.query,
        "chunks": items,
        "latency_ms": round(latency_ms, 2),
    }).model_dump()
