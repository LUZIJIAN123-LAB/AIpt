"""Sentence/paragraph-aware text chunker.

Strategy (matches the resume line "chunk 800 / overlap 100"):
    1. Split source text into paragraphs (blank-line separators).
    2. Merge paragraphs until the accumulator reaches `chunk_size` — never
       split inside a paragraph.  If a paragraph alone is longer than `chunk_size`,
       split *that paragraph* by Chinese sentence boundary (。！？) / ASCII sentence
       boundary (. ! ?).
    3. The final `overlap` characters from chunk N are prepended to chunk N+1,
       so the next chunk starts with the tail of the previous chunk.

Output aligns directly with the `chunks` DB table:
    ChunkInfo(index, content, start_offset, end_offset, chunk_type)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.core.config import settings
from app.services.parser import Block, ParsedDocument


@dataclass
class ChunkInfo:
    """One output chunk — 1:1 maps to app.db.models.Chunk columns."""
    index: int                          # 0-based
    content: str                        # Full chunk text (includes overlap prefix when applicable)
    start_offset: int                   # Char offset inside *original* doc text
    end_offset: int                     # Exclusive
    chunk_type: str = "text"            # text | heading | code | list | table


# --- Public API ---

def chunk_document(
    parsed: ParsedDocument,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[ChunkInfo]:
    """Chunk a parsed document. Uses RAG_CHUNK_SIZE / RAG_CHUNK_OVERLAP from settings if not given."""
    cs = chunk_size or settings.RAG_CHUNK_SIZE
    ov = overlap or settings.RAG_CHUNK_OVERLAP
    return _chunk_from_blocks(parsed.blocks, parsed.text, cs, ov)


def chunk_plain_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[ChunkInfo]:
    """Convenience: chunk raw text directly (used for tests and non-document queries)."""
    cs = chunk_size or settings.RAG_CHUNK_SIZE
    ov = overlap or settings.RAG_CHUNK_OVERLAP
    blocks = [Block(text=p, type="text") for p in re.split(r"\n\s*\n+", text) if p.strip()]
    return _chunk_from_blocks(blocks, text, cs, ov)


# --- Internals ---

_SENT_SPLIT_RE = re.compile(r"(?<=[。！？.!?])\s+|(?<=[。！？.!?])")


def _split_long_paragraph(text: str, limit: int) -> list[str]:
    """Split a single oversized paragraph by sentence boundaries, falling back to char limit."""
    if len(text) <= limit:
        return [text]

    # Primary: sentence-boundary split.
    parts = _SENT_SPLIT_RE.split(text)
    merged: list[str] = []
    cur = ""
    for p in parts:
        if not p:
            continue
        if len(cur) + len(p) <= limit:
            cur += p
        else:
            if cur:
                merged.append(cur)
            # If one sentence alone is > limit, hard-split by char.
            if len(p) > limit:
                for i in range(0, len(p), limit):
                    merged.append(p[i : i + limit])
                cur = ""
            else:
                cur = p
    if cur:
        merged.append(cur)
    return merged


def _find_offset(original: str, content: str, hint: int) -> int:
    """Find `content` inside `original` starting from `hint` (fast-forward) position."""
    pos = original.find(content, hint)
    if pos == -1:
        # Fallback: linear scan from start (rare).
        pos = original.find(content)
    return pos if pos != -1 else hint


def _chunk_from_blocks(
    blocks: Iterable[Block],
    original_text: str,
    chunk_size: int,
    overlap: int,
) -> list[ChunkInfo]:
    chunks: list[ChunkInfo] = []
    current_parts: list[str] = []   # pieces accumulated into the current chunk
    current_len = 0                 # total chars of current_parts (no overlap yet)
    idx = 0
    offset_hint = 0
    prev_tail = ""                  # last `overlap` chars of previous chunk

    for block in blocks:
        # Long block → pre-split at sentence boundaries.
        for piece in _split_long_paragraph(block.text, chunk_size):
            # If this piece alone is bigger than chunk_size (very long code line), keep it whole.
            if current_len + len(piece) <= chunk_size:
                current_parts.append(piece)
                current_len += len(piece)
                continue

            # Flush current.
            if current_parts:
                chunk_text = prev_tail + "".join(current_parts)
                start = _find_offset(original_text, current_parts[0], offset_hint)
                end = _find_offset(original_text, current_parts[-1], start) + len(current_parts[-1])
                chunks.append(ChunkInfo(
                    index=idx,
                    content=chunk_text,
                    start_offset=start,
                    end_offset=end,
                    chunk_type=_merge_chunk_type(current_parts),
                ))
                offset_hint = end
                idx += 1
                prev_tail = chunk_text[-overlap:] if len(chunk_text) > overlap else chunk_text
                current_parts = []
                current_len = 0

            # Start new chunk with this piece (possibly prefixed by prev_tail logic above).
            current_parts.append(piece)
            current_len = len(piece)

    # Final flush.
    if current_parts:
        chunk_text = prev_tail + "".join(current_parts)
        start = _find_offset(original_text, current_parts[0], offset_hint)
        end = _find_offset(original_text, current_parts[-1], start) + len(current_parts[-1])
        chunks.append(ChunkInfo(
            index=idx,
            content=chunk_text,
            start_offset=start,
            end_offset=end,
            chunk_type=_merge_chunk_type(current_parts),
        ))

    return chunks


def _merge_chunk_type(parts: list[str]) -> str:
    """Best-effort chunk_type from piece content (used when we lose the Block.type info)."""
    first = parts[0].strip()
    if first.startswith("#") or len(first) < 40 and not first.endswith((".", "。", "!", "！")):
        return "heading"
    if "def " in first or "class " in first or first.startswith(("{", "function ", "const ")):
        return "code"
    return "text"
