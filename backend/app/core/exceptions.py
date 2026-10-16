"""Unified exception hierarchy + FastAPI exception handlers.

Every raised exception maps to a JSON response with {code, message, detail}.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.responses import ErrorResponse


class AppError(Exception):
    """Base exception — carries HTTP status + business error code."""

    http_status: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "Internal server error"

    def __init__(self, message: str | None = None, detail: Any = None):
        self.message = message or self.__class__.message
        self.detail = detail
        super().__init__(self.message)


# --- 4xx Client Errors ---

class BadRequestError(AppError):
    http_status = 400
    code = "BAD_REQUEST"
    message = "Bad request"


class NotFoundError(AppError):
    http_status = 404
    code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(AppError):
    http_status = 409
    code = "CONFLICT"
    message = "Resource conflict"


class ValidationFailedError(AppError):
    """Raised when a Pydantic or business validation fails *past* the router layer."""

    http_status = 422
    code = "VALIDATION_FAILED"
    message = "Validation failed"


class UnsupportedFileTypeError(BadRequestError):
    code = "UNSUPPORTED_FILE_TYPE"
    message = "Unsupported file type"


# --- 5xx Server Errors ---

class ServiceUnavailableError(AppError):
    http_status = 503
    code = "SERVICE_UNAVAILABLE"
    message = "Upstream service unavailable"


class LLMError(ServiceUnavailableError):
    code = "LLM_ERROR"
    message = "LLM provider call failed"


class EmbeddingError(ServiceUnavailableError):
    code = "EMBEDDING_ERROR"
    message = "Embedding service failed"


# --- Handler Registration ---

def register_exception_handlers(app: FastAPI) -> None:
    """Wire handlers into the FastAPI app — called once in main.py."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        payload = ErrorResponse(
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
        )
        return JSONResponse(status_code=exc.http_status, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        payload = ErrorResponse(
            code="VALIDATION_FAILED",
            message="Request validation failed",
            detail=exc.errors(),
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def _unexpected_handler(_: Request, exc: Exception) -> JSONResponse:
        # Logged by loguru middleware in main.py; here we just mask the detail.
        payload = ErrorResponse(
            code="INTERNAL_ERROR",
            message="Internal server error",
            detail=str(exc) if app.state.settings.APP_ENV == "dev" else None,
        )
        return JSONResponse(status_code=500, content=payload.model_dump())
