"""Voice preset API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import DbSession, CurrentUser
from src.schemas.voice_preset import (
    VoicePresetCreate,
    VoicePresetUpdate,
    VoicePresetResponse,
    VoicePresetListResponse,
)
from src.services.voice_preset_service import VoicePresetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice-presets", tags=["voice-presets"])


@router.get("", response_model=VoicePresetListResponse)
async def list_voice_presets(
    db: DbSession,
    current_user: CurrentUser,
    type: str | None = Query(None, description="Filter by type: 'tts' or 'stt'"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """List voice presets for the current user."""
    service = VoicePresetService(db)
    items, total = await service.list(
        user_id=current_user.id,
        type_filter=type,
        page=page,
        page_size=page_size,
    )
    return VoicePresetListResponse(
        items=[VoicePresetResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("", response_model=VoicePresetResponse, status_code=status.HTTP_201_CREATED)
async def create_voice_preset(
    data: VoicePresetCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new voice preset."""
    service = VoicePresetService(db)
    preset = await service.create(user_id=current_user.id, data=data)
    return VoicePresetResponse.model_validate(preset)


@router.get("/{preset_id}", response_model=VoicePresetResponse)
async def get_voice_preset(
    preset_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a voice preset by ID."""
    service = VoicePresetService(db)
    preset = await service.get(preset_id, user_id=current_user.id)
    return VoicePresetResponse.model_validate(preset)


@router.patch("/{preset_id}", response_model=VoicePresetResponse)
async def update_voice_preset(
    preset_id: UUID,
    data: VoicePresetUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update a voice preset."""
    service = VoicePresetService(db)
    preset = await service.update(preset_id, user_id=current_user.id, data=data)
    return VoicePresetResponse.model_validate(preset)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_preset(
    preset_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    """Delete a voice preset."""
    service = VoicePresetService(db)
    await service.delete(preset_id, user_id=current_user.id)
