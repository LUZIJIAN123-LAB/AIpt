"""Auth endpoints — register, login, me.

All responses are wrapped in SuccessResponse envelope (consistent with other
endpoints). Frontend `unwrap<T>()` strips it transparently.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.responses import SuccessResponse
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.models.user import User
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/auth")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    display_name: str | None = Field(None, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserPublic(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    is_active: bool

    @classmethod
    def from_orm(cls, u: User) -> "UserPublic":
        return cls(
            id=str(u.id),
            username=u.username,
            display_name=u.display_name,
            is_active=u.is_active,
        )


class AuthResponse(BaseModel):
    token: TokenResponse
    user: UserPublic


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
async def _create_user(
    session: AsyncSession,
    username: str,
    password: str,
    display_name: str | None = None,
) -> User:
    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=SuccessResponse[AuthResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest) -> dict:
    async with AsyncSessionLocal() as session:
        user = await _create_user(session, payload.username, payload.password, payload.display_name)
    payload_out = AuthResponse(
        token=TokenResponse(
            access_token=create_access_token(user.id),
            expires_in=settings.AUTH_JWT_EXPIRE_MINUTES * 60,
        ),
        user=UserPublic.from_orm(user),
    )
    return SuccessResponse(data=payload_out).model_dump()


@router.post(
    "/login",
    response_model=SuccessResponse[AuthResponse],
)
async def login(payload: LoginRequest) -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == payload.username)
        )
        user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload_out = AuthResponse(
        token=TokenResponse(
            access_token=create_access_token(user.id),
            expires_in=settings.AUTH_JWT_EXPIRE_MINUTES * 60,
        ),
        user=UserPublic.from_orm(user),
    )
    return SuccessResponse(data=payload_out).model_dump()


@router.get(
    "/me",
    response_model=SuccessResponse[UserPublic],
)
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return SuccessResponse(data=UserPublic.from_orm(current_user)).model_dump()
