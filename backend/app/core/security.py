"""Auth primitives — bcrypt password hashing, JWT encode/decode, FastAPI deps."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models.user import User


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    """Issue a short-lived access token. `subject` is usually user.id (str)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.AUTH_JWT_EXPIRE_MINUTES)).timestamp()),
        "iss": settings.APP_NAME,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.AUTH_JWT_SECRET, algorithm=settings.AUTH_JWT_ALGO)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.AUTH_JWT_SECRET,
            algorithms=[settings.AUTH_JWT_ALGO],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e


# ---------------------------------------------------------------------------
# FastAPI deps
# ---------------------------------------------------------------------------
async def _get_user_from_db(user_id: str, session: AsyncSession) -> User | None:
    try:
        from uuid import UUID
        uid = UUID(user_id)
    except ValueError:
        return None
    result = await session.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


async def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
) -> User:
    """Strict — raise 401 if token missing/bad/user gone."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    async with AsyncSessionLocal() as session:
        user = await _get_user_from_db(payload["sub"], session)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_optional_user(
    token: str | None = Depends(_oauth2_scheme),
) -> User | None:
    """Permissive — returns None if no auth, still validates token if present."""
    if not token:
        return None
    payload = decode_access_token(token)
    async with AsyncSessionLocal() as session:
        user = await _get_user_from_db(payload["sub"], session)
    if user is None or not user.is_active:
        return None
    return user
