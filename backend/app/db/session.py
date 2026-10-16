"""SQLAlchemy 2.0 async engine + session factory.

Usage in routers:
    from app.db.session import get_db
    async def foo(db: AsyncSession = Depends(get_db)): ...
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect  # noqa: F401

# --- Engine & session factory ---
# lazy=False → construct eagerly so we can .dispose() on shutdown.
engine: AsyncEngine = create_async_engine(
    settings.dsn,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=(settings.APP_ENV == "dev"),
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a scoped async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_engine() -> None:
    """Called from FastAPI lifespan on shutdown."""
    await engine.dispose()
