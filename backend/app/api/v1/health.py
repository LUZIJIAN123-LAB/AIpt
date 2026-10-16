"""Health-check endpoint — simplest endpoint to validate the whole scaffold."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.responses import SuccessResponse

router = APIRouter(prefix="/health")


@router.get(
    "",
    response_model=SuccessResponse[dict],
    summary="Service health check",
)
async def health_check() -> dict:
    """Lightweight liveness probe — no DB call so it works before PostgreSQL is up."""
    return SuccessResponse(
        data={
            "name": settings.APP_NAME,
            "env": settings.APP_ENV,
            "status": "ok",
        }
    ).model_dump()
