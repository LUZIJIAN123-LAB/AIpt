"""Conversation CRUD endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.core.responses import SuccessResponse
from app.schemas import ConversationCreate
from app.services import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)

router = APIRouter(prefix="/conversations")


@router.post("", summary="Create a new conversation")
async def create(body: ConversationCreate) -> dict:
    return SuccessResponse(data=await create_conversation(body)).model_dump()


@router.get("", summary="List conversations (paginated)")
async def list_api(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    items, total = await list_conversations(page=page, page_size=page_size)
    return SuccessResponse(data={
        "items": items, "total": total, "page": page, "page_size": page_size,
    }).model_dump()


@router.get("/{conv_id}", summary="Conversation detail with messages")
async def get_api(conv_id: UUID) -> dict:
    return SuccessResponse(data=await get_conversation(conv_id)).model_dump()


@router.delete("/{conv_id}", summary="Delete conversation + all messages")
async def delete_api(conv_id: UUID) -> dict:
    await delete_conversation(conv_id)
    return SuccessResponse(data={"id": str(conv_id)}).model_dump()
