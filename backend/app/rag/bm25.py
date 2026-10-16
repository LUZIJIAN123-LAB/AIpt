"""Lightweight in-memory BM25 — pure Python, no external deps.

Designed specifically for the RAG pipeline in this repo:
    * index_batch(chunks: list[str])         -> BM25Index
    * bm25_index.search(query, top_k=10)     -> list[(idx, score)]
    * bm25_index.multi_search(query_vec, ...)-> as above but for batch queries

Tokenization rule (keeps BM25 simple and Chinese-friendly):
    * ASCII alphanumeric runs are tokens -> "hello world 2024" -> ["hello", "world", "2024"]
    * CJK characters are individual tokens -> "检索" -> ["检", "索"]

This is not state-of-the-art but it is correct for mixed Chinese/English text,
fast enough for Top-K retrieval on <100k chunks (single-threaded microseconds),
and avoids pulling Elasticsearch/jieba into the 2C4G deployment image.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

# --- Tokenization ---

_ASCII_RE = re.compile(r"[A-Za-z0-9]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """Split a chunk into tokens — handles CJK single chars + ASCII words."""
    if not text:
        return []
    tokens: list[str] = []
    # Lowercase ASCII, split non-word chars into separate CJK chars.
    text = text.lower()
    pos = 0
    n = len(text)
    while pos < n:
        if text[pos].isascii():
            m = _ASCII_RE.match(text, pos)
            if m:
                tokens.append(m.group())
                pos = m.end()
                continue
            pos += 1  # skip non-word ASCII (punct, whitespace)
        elif _CJK_RE.match(text, pos):
            tokens.append(text[pos])
            pos += 1
        else:
            pos += 1  # skip numbers / symbols in CJK zones if any
    return tokens


# --- BM25 ---

@dataclass
class BM25Index:
    """In-memory BM25 index — call index_batch() once, then search() repeatedly."""

    doc_count: int = 0
    avgdl: float = 0.0
    # idf[token] = idf value (precomputed at index time)
    idf: dict[str, float] = field(default_factory=dict)
    # Per-document data — parallel to the input chunk list.
    doc_tokens: list[Counter[str]] = field(default_factory=list)
    doc_lengths: list[int] = field(default_factory=list)

    k1: float = 1.5   # BM25 term frequency saturation
    b: float = 0.75   # BM25 length normalization


def build_bm25(chunks: Sequence[str], *, k1: float = 1.5, b: float = 0.75) -> BM25Index:
    """Build a BM25 index from a batch of chunk strings."""
    idx = BM25Index(k1=k1, b=b)
    idx.doc_count = len(chunks)
    if idx.doc_count == 0:
        return idx

    idx.doc_tokens = [Counter(tokenize(c)) for c in chunks]
    idx.doc_lengths = [sum(c.values()) for c in idx.doc_tokens]
    idx.avgdl = sum(idx.doc_lengths) / idx.doc_count

    # Document frequency for each token — number of docs containing it.
    df: Counter[str] = Counter()
    for counter in idx.doc_tokens:
        df.update(counter.keys())

    # IDF: log((N - df + 0.5) / (df + 0.5) + 1)  — standard BM25 smoothing.
    N = idx.doc_count
    idx.idf = {
        t: math.log((N - df_t + 0.5) / (df_t + 0.5) + 1.0)
        for t, df_t in df.items()
    }
    return idx


def bm25_search(
    index: BM25Index,
    query: str,
    *,
    top_k: int = 10,
    min_score: float = 0.0,
) -> list[tuple[int, float]]:
    """Run a BM25 query against the index. Returns sorted [(doc_idx, score)]."""
    if index.doc_count == 0:
        return []

    q_tokens = tokenize(query)
    if not q_tokens:
        return []

    scores: list[float] = [0.0] * index.doc_count
    k1, b = index.k1, index.b
    avgdl = index.avgdl
    idf = index.idf
    N = index.doc_count

    # For each query token, accumulate score across all docs.
    for t in q_tokens:
        idf_t = idf.get(t)
        if idf_t is None:
            continue  # token never seen — skip (zero contribution)
        for i in range(N):
            f_td = index.doc_tokens[i].get(t, 0)
            if f_td == 0:
                continue
            dl = index.doc_lengths[i]
            denom = f_td + k1 * (1 - b + b * (dl / avgdl if avgdl > 0 else 0))
            scores[i] += idf_t * (f_td * (k1 + 1)) / denom

    # Pair with index, filter out zero-score docs, sort descending.
    ranked = [
        (i, scores[i])
        for i in range(N)
        if scores[i] > min_score
    ]
    ranked.sort(key=lambda x: -x[1])
    return ranked[:top_k]


# --- Similarity ---

def normalize_scores(pairs: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Min-max normalize a list of (idx, score) pairs to [0, 1]."""
    if not pairs:
        return []
    scores = [s for _, s in pairs]
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-12:
        return [(i, 1.0) for i, _ in pairs]
    return [(i, (s - lo) / (hi - lo)) for i, s in pairs]
