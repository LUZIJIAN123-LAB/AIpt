"""API v1 package — all routes are registered here."""

from fastapi import APIRouter

from app.api.v1.ask import router as ask_router
from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.search import router as search_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(health_router, tags=["system"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(search_router, tags=["retrieval"])
api_router.include_router(conversations_router, tags=["conversations"])
api_router.include_router(ask_router, tags=["ask"])

__all__ = ["api_router"]
