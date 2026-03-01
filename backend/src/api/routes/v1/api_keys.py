"""API Key management routes."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import DbSession, CurrentUser
from src.models.api_key import APIKey


router = APIRouter()


# ==================== Schemas ====================

class APIKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: str
    last_used_at: str | None
    expires_at: str | None
    scopes: list[str]

    class Config:
        from_attributes = True


class APIKeyCreateRequest(BaseModel):
    name: str
    expires_in: int | None = None  # days


class APIKeyCreateResponse(BaseModel):
    key: str
    id: str
    name: str
    prefix: str


# ==================== Helpers ====================

def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _to_response(key: APIKey) -> APIKeyResponse:
    return APIKeyResponse(
        id=str(key.id),
        name=key.name,
        prefix=key.key_prefix,
        created_at=key.created_at.isoformat() if key.created_at else "",
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
        scopes=[key.permissions] if key.permissions else ["full"],
    )


# ==================== Routes ====================

@router.get("")
async def list_api_keys(
    db: DbSession,
    user: CurrentUser,
) -> list[APIKeyResponse]:
    """List all API keys for the current user."""
    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user.id, APIKey.is_active == True)
        .order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [_to_response(k) for k in keys]


@router.post("", status_code=201)
async def create_api_key(
    data: APIKeyCreateRequest,
    db: DbSession,
    user: CurrentUser,
) -> APIKeyCreateResponse:
    """Create a new API key. The raw key is only returned once."""
    raw_key = f"sk-{secrets.token_urlsafe(32)}"
    prefix = raw_key[:8] + "..." + raw_key[-4:]

    expires_at = None
    if data.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in)

    api_key = APIKey(
        user_id=user.id,
        name=data.name,
        key_hash=_hash_key(raw_key),
        key_prefix=prefix,
        permissions="full",
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    return APIKeyCreateResponse(
        key=raw_key,
        id=str(api_key.id),
        name=api_key.name,
        prefix=prefix,
    )


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Delete (deactivate) an API key."""
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    key.is_active = False
    await db.flush()
