"""LLM Vendor Key management routes.

Users can save/list/delete their own LLM vendor API keys.
Keys are encrypted at rest and never returned in full.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import DbSession, CurrentUser
from src.services import llm_key_service

router = APIRouter()


class SaveLLMKeyRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    api_key: str = Field(..., min_length=1)
    label: str | None = None


class LLMKeyResponse(BaseModel):
    provider: str
    key_preview: str
    label: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LLMKeyListResponse(BaseModel):
    keys: list[LLMKeyResponse]


@router.get("", response_model=LLMKeyListResponse)
async def list_llm_keys(
    db: DbSession,
    current_user: CurrentUser,
) -> LLMKeyListResponse:
    """List saved vendor keys (masked preview, never full key)."""
    keys = await llm_key_service.list_user_llm_keys(db, current_user.id)
    return LLMKeyListResponse(keys=keys)


@router.post("", response_model=LLMKeyResponse)
async def save_llm_key(
    request: SaveLLMKeyRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> LLMKeyResponse:
    """Save or upsert an encrypted LLM vendor key."""
    row = await llm_key_service.save_llm_key(
        db=db,
        user_id=current_user.id,
        provider=request.provider,
        api_key=request.api_key,
        label=request.label,
    )
    # Return masked preview
    preview = llm_key_service.mask_key(request.api_key)
    return LLMKeyResponse(
        provider=row.provider,
        key_preview=preview,
        label=row.label,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.delete("/{provider}")
async def delete_llm_key(
    provider: str,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Remove a saved LLM vendor key."""
    deleted = await llm_key_service.delete_user_llm_key(
        db, current_user.id, provider
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No key found for provider: {provider}",
        )
    return {"deleted": True}
