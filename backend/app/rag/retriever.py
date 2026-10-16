"""Hybrid retriever — vector top-K + BM25 top-K → dedupe → weighted rerank → final top-K.

Pure in-memory (no DB) for local dev / tests. When PostgreSQL + pgvector are online
Step 5b in the real pipeline will swap `_vector_search_in_memory` for a real
SQLAlchemy query using `Chunk.embedding.cosine_distance(query_vec)`.

Weighted rerank formula:
    final_score = alpha * norm(vector_score) + beta  * norm(bm25_score)

Both scores are min-max normalized to [0, 1] before combining.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from app.rag.bm25 import (
    BM25Index,
    build_bm25,
    bm25_search,
    normalize_scores,
)


@dataclass
class RetrievedChunk:
    """One result from hybrid retrieval — carries both scores for explainability."""
    index: int                      # position in the original chunks list
    content: str
    vector_score: float = 0.0       # cosine similarity (higher = more similar)
    bm25_score: float = 0.0         # raw BM25 score
    final_score: float = 0.0        # weighted sum
    source: str = ""                # "vector" | "bm25" | "hybrid"


@dataclass
class HybridIndex:
    """Holds both embeddings + BM25 index — built once, queried many times."""
    chunks: list[str]
    embeddings: np.ndarray          # shape (n, dim), L2-normalized
    bm25: BM25Index
    k_vector: int = 10
    k_bm25: int = 10
    k_final: int = 6
    alpha: float = 0.6              # weight on vector score
    beta: float = 0.4               # weight on BM25 score

    def search(self, query: str, query_vec: list[float]) -> list[RetrievedChunk]:
        return hybrid_search(self, query, query_vec)


def build_hybrid_index(
    chunks: Sequence[str],
    embeddings: list[list[float]],
    *,
    k_vector: int = 10,
    k_bm25: int = 10,
    k_final: int = 6,
    alpha: float = 0.6,
    beta: float = 0.4,
) -> HybridIndex:
    """Create both indices from scratch. Embeddings are L2-normalized in-place."""
    arr = np.array(embeddings, dtype=np.float32)
    # L2-normalize rows so dot product == cosine similarity.
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    # Guard against zero-norm vectors.
    norms[norms == 0] = 1.0
    arr = arr / norms

    bm25 = build_bm25(list(chunks))

    return HybridIndex(
        chunks=list(chunks),
        embeddings=arr,
        bm25=bm25,
        k_vector=k_vector,
        k_bm25=k_bm25,
        k_final=k_final,
        alpha=alpha,
        beta=beta,
    )


# --- Public search ---

def hybrid_search(
    h: HybridIndex,
    query: str,
    query_vec: list[float],
) -> list[RetrievedChunk]:
    """Run vector top-K + BM25 top-K, merge and rerank."""
    n = len(h.chunks)
    if n == 0:
        return []

    # --- 1. Vector top-K (cosine similarity via dot product on L2-normalized rows) ---
    vec_arr = np.array(query_vec, dtype=np.float32)
    vn = np.linalg.norm(vec_arr)
    if vn > 0:
        vec_arr = vec_arr / vn
    sims = h.embeddings @ vec_arr  # shape (n,)
    # Take top k_vector indices by descending similarity.
    vec_top_k = min(h.k_vector, n)
    vec_order = np.argsort(-sims)[:vec_top_k]
    vec_results = [(int(i), float(sims[i])) for i in vec_order]

    # --- 2. BM25 top-K ---
    bm25_results = bm25_search(h.bm25, query, top_k=h.k_bm25)

    # --- 3. Merge + dedupe (union of both sets, retaining best seen score per idx) ---
    merged: dict[int, RetrievedChunk] = {}
    for idx, score in vec_results:
        merged[idx] = RetrievedChunk(
            index=idx,
            content=h.chunks[idx],
            vector_score=score,
        )
    for idx, score in bm25_results:
        if idx in merged:
            merged[idx].bm25_score = score
        else:
            merged[idx] = RetrievedChunk(
                index=idx,
                content=h.chunks[idx],
                bm25_score=score,
            )

    # --- 4. Weighted rerank ---
    vec_pairs = [(r.index, r.vector_score) for r in merged.values() if r.vector_score != 0.0]
    bm25_pairs = [(r.index, r.bm25_score) for r in merged.values() if r.bm25_score != 0.0]

    vec_norm = dict(normalize_scores(vec_pairs)) if vec_pairs else {}
    bm25_norm = dict(normalize_scores(bm25_pairs)) if bm25_pairs else {}

    for idx, r in merged.items():
        v = vec_norm.get(idx, 0.0)
        b = bm25_norm.get(idx, 0.0)
        r.final_score = h.alpha * v + h.beta * b
        sources = []
        if idx in vec_norm:
            sources.append("vector")
        if idx in bm25_norm:
            sources.append("bm25")
        r.source = "+".join(sources) if sources else "hybrid"

    ranked = sorted(merged.values(), key=lambda r: -r.final_score)
    return ranked[:h.k_final]
