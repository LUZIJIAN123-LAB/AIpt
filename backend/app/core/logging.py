"""Loguru-based logging setup — one callable install_logging() in main.py."""
from __future__ import annotations

import sys

from loguru import logger

from app.core.config import settings


def install_logging() -> None:
    """Configure loguru once at process start. Idempotent."""
    logger.remove()

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    level = "DEBUG" if settings.APP_ENV == "dev" else "INFO"

    logger.add(
        sys.stdout,
        level=level,
        format=fmt,
        colorize=True,
        backtrace=settings.APP_ENV == "dev",
        diagnose=settings.APP_ENV == "dev",
    )
