"""Unified API response envelope.

Every endpoint returns either a SuccessResponse or raises an AppError
which is caught by handlers and turned into an ErrorResponse.
"""
from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success body — wraps the actual payload in `data`."""

    model_config = ConfigDict(extra="forbid")

    code: Literal["OK"] = "OK"
    message: str = "success"
    data: T | None = None


class ErrorResponse(BaseModel):
    """Standard error body — `detail` carries structured debug info."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Business error code, e.g. NOT_FOUND")
    message: str = Field(..., description="Human-readable error message")
    detail: Any = Field(default=None, description="Debug detail (dev only)")


# --- Factory helpers ---

def ok(data: Any = None, message: str = "success") -> dict:
    """Convenience shortcut — returns a dict FastAPI will serialize as JSON."""
    return SuccessResponse(data=data, message=message).model_dump()


def fail(code: str, message: str, detail: Any = None) -> dict:
    """Rarely needed — prefer raising an AppError subclass."""
    return ErrorResponse(code=code, message=message, detail=detail).model_dump()
