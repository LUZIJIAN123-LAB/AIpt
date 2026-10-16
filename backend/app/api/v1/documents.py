"""Document endpoints — upload / list / detail / delete."""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.core.responses import SuccessResponse
from app.services import (
    delete_document,
    ingest_upload,
    list_documents,
    save_upload_to_temp,
    get_document as _get_document,
)

router = APIRouter(prefix="/documents")


@router.post("/upload", summary="Upload + parse + embed a document")
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> dict:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    tmp_path = save_upload_to_temp(file_bytes, file.filename or "unknown")
    try:
        result = await ingest_upload(tmp_path, file.filename or "unknown", title=title)
    finally:
        tmp_path.unlink(missing_ok=True)

    if result.get("skipped"):
        return SuccessResponse(
            code="OK",
            message="Document already ingested (duplicate file_hash)",
            data=result,
        ).model_dump()

    return SuccessResponse(data=result).model_dump()


@router.get("", summary="List documents (paginated)")
async def list_documents_api(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    items, total = await list_documents(page=page, page_size=page_size)
    return SuccessResponse(data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }).model_dump()


@router.get("/{doc_id}", summary="Document detail with chunks")
async def get_document(doc_id: UUID) -> dict:
    data = await _get_document(doc_id)
    return SuccessResponse(data=data).model_dump()


@router.delete("/{doc_id}", summary="Delete document + its chunks")
async def delete_document_api(doc_id: UUID) -> dict:
    await delete_document(doc_id)
    return SuccessResponse(data={"id": str(doc_id)}).model_dump()
