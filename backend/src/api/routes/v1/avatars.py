"""Avatar API routes for avatar management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.deps import DbSession, CurrentUser
from src.models.avatar import Avatar, SYSTEM_AVATARS

router = APIRouter(tags=["avatars"])


# ====================
# Pydantic Schemas
# ====================


class AvatarAppearance(BaseModel):
    gender: str | None = None
    ethnicity: str | None = None
    age_range: str | None = None
    style: str | None = None
    outfit: str | None = None
    background: str | None = None


class AvatarModelConfig(BaseModel):
    model_url: str | None = None
    animations: dict | None = None
    morph_targets: list[str] | None = None
    camera_position: list[float] | None = None
    lighting: str | None = None


class AvatarHeyGenConfig(BaseModel):
    avatar_id: str | None = None
    voice_id: str | None = None
    quality: str = "high"
    background_type: str = "transparent"


class AvatarVoiceConfig(BaseModel):
    provider: str = "elevenlabs"
    voice_id: str | None = None
    language: str = "en-US"
    speaking_rate: float = 1.0
    pitch: float = 0.0
    style: str = "friendly"
    emotion: str = "neutral"


class AvatarPersonality(BaseModel):
    tone: str = "professional"
    empathy_level: str = "medium"
    humor: str = "subtle"
    patience: str = "high"
    assertiveness: str = "medium"


class CreateAvatarRequest(BaseModel):
    name: str
    description: str | None = None
    category: str = "general"
    avatar_type: str = "3d"
    appearance: AvatarAppearance | None = None
    avatar_model_settings: AvatarModelConfig | None = None
    heygen_config: AvatarHeyGenConfig | None = None
    voice_config: AvatarVoiceConfig | None = None
    personality: AvatarPersonality | None = None
    system_prompt_prefix: str | None = None
    greetings: list[str] | None = None
    thumbnail_url: str | None = None
    preview_video_url: str | None = None
    tags: list[str] | None = None
    is_public: bool = False


class UpdateAvatarRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    avatar_type: str | None = None
    appearance: AvatarAppearance | None = None
    avatar_model_settings: AvatarModelConfig | None = None
    heygen_config: AvatarHeyGenConfig | None = None
    voice_config: AvatarVoiceConfig | None = None
    personality: AvatarPersonality | None = None
    system_prompt_prefix: str | None = None
    greetings: list[str] | None = None
    thumbnail_url: str | None = None
    preview_video_url: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None
    is_public: bool | None = None


class AvatarResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    category: str
    avatar_type: str
    appearance: dict
    avatar_model_settings: dict = Field(validation_alias="model_config")
    heygen_config: dict
    voice_config: dict
    personality: dict
    system_prompt_prefix: str | None
    greetings: list[str]
    thumbnail_url: str | None
    preview_video_url: str | None
    tags: list[str]
    is_active: bool
    is_public: bool
    is_system: bool

    class Config:
        from_attributes = True
        populate_by_name = True


# ====================
# Avatar Endpoints
# ====================


@router.get("/system", response_model=list[dict])
async def list_system_avatars():
    """List all system-provided avatars (pre-defined templates)."""
    return SYSTEM_AVATARS


@router.get("/categories")
async def list_avatar_categories():
    """List available avatar categories."""
    return {
        "categories": [
            {"id": "general", "name": "General", "description": "General purpose assistants"},
            {"id": "hr", "name": "Human Resources", "description": "HR specialists and employee support"},
            {"id": "finance", "name": "Finance", "description": "Financial advisors and analysts"},
            {"id": "sales", "name": "Sales", "description": "Sales representatives and account managers"},
            {"id": "support", "name": "Support", "description": "Customer support specialists"},
            {"id": "technical", "name": "Technical", "description": "IT support and technical experts"},
            {"id": "executive", "name": "Executive", "description": "Executive assistants and managers"},
            {"id": "custom", "name": "Custom", "description": "Custom-designed avatars"},
        ]
    }


@router.get("/types")
async def list_avatar_types():
    """List available avatar types."""
    return {
        "types": [
            {
                "id": "3d",
                "name": "3D Avatar",
                "description": "Interactive 3D model with animations and lip-sync",
                "features": ["lip-sync", "animations", "morph-targets", "custom-backgrounds"],
            },
            {
                "id": "heygen",
                "name": "HeyGen Avatar",
                "description": "Photorealistic AI avatar powered by HeyGen",
                "features": ["photorealistic", "natural-expressions", "multiple-languages"],
            },
            {
                "id": "video",
                "name": "Video Avatar",
                "description": "Pre-recorded video clips with audio sync",
                "features": ["custom-recording", "branded-content"],
            },
            {
                "id": "animated",
                "name": "Animated Avatar",
                "description": "2D animated character with expressions",
                "features": ["lightweight", "fast-loading", "customizable"],
            },
            {
                "id": "simple",
                "name": "Simple Avatar",
                "description": "Static image with audio indicator",
                "features": ["minimal", "fast", "accessible"],
            },
        ]
    }


@router.get("", response_model=list[AvatarResponse])
async def list_avatars(
    db: DbSession,
    current_user: CurrentUser,
    category: str | None = None,
    avatar_type: str | None = None,
    include_system: bool = True,
):
    """List all available avatars."""
    query = select(Avatar).where(
        Avatar.is_active == True,
    )

    if category:
        query = query.where(Avatar.category == category)
    if avatar_type:
        query = query.where(Avatar.avatar_type == avatar_type)
    if not include_system:
        query = query.where(Avatar.is_system == False)

    result = await db.execute(query.order_by(Avatar.name))
    avatars = list(result.scalars().all())

    return avatars


@router.post("", response_model=AvatarResponse, status_code=status.HTTP_201_CREATED)
async def create_avatar(
    request: CreateAvatarRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new avatar."""
    avatar = Avatar(
        name=request.name,
        description=request.description,
        category=request.category,
        avatar_type=request.avatar_type,
        appearance=request.appearance.model_dump() if request.appearance else {},
        model_config=request.avatar_model_settings.model_dump() if request.avatar_model_settings else {},
        heygen_config=request.heygen_config.model_dump() if request.heygen_config else {},
        voice_config=request.voice_config.model_dump() if request.voice_config else {},
        personality=request.personality.model_dump() if request.personality else {},
        system_prompt_prefix=request.system_prompt_prefix,
        greetings=request.greetings or [],
        thumbnail_url=request.thumbnail_url,
        preview_video_url=request.preview_video_url,
        tags=request.tags or [],
        is_public=request.is_public,
    )

    db.add(avatar)
    await db.flush()

    return avatar


@router.get("/{avatar_id}", response_model=AvatarResponse)
async def get_avatar(
    avatar_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific avatar by ID."""
    result = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    avatar = result.scalar_one_or_none()

    if not avatar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )

    return avatar


@router.put("/{avatar_id}", response_model=AvatarResponse)
async def update_avatar(
    avatar_id: UUID,
    request: UpdateAvatarRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update an existing avatar."""
    result = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    avatar = result.scalar_one_or_none()

    if not avatar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )

    if avatar.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify system avatars",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)

    # Map Pydantic field name to SQLAlchemy column name
    field_mapping = {
        "avatar_model_settings": "model_config",
    }

    for field, value in update_data.items():
        if value is not None:
            if hasattr(value, "model_dump"):
                value = value.model_dump()
            # Use mapped field name if exists
            db_field = field_mapping.get(field, field)
            setattr(avatar, db_field, value)

    await db.flush()
    return avatar


@router.delete("/{avatar_id}")
async def delete_avatar(
    avatar_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    """Delete an avatar."""
    result = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    avatar = result.scalar_one_or_none()

    if not avatar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )

    if avatar.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system avatars",
        )

    avatar.is_active = False
    await db.flush()

    return {"message": "Avatar deleted successfully"}


@router.post("/{avatar_id}/clone", response_model=AvatarResponse)
async def clone_avatar(
    avatar_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    new_name: str | None = None,
):
    """Clone an avatar."""
    # Get source avatar
    result = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )

    # Create clone
    clone = Avatar(
        name=new_name or f"{source.name} (Copy)",
        description=source.description,
        category=source.category,
        avatar_type=source.avatar_type,
        appearance=source.appearance.copy() if source.appearance else {},
        model_config=source.model_config.copy() if source.model_config else {},
        heygen_config=source.heygen_config.copy() if source.heygen_config else {},
        voice_config=source.voice_config.copy() if source.voice_config else {},
        personality=source.personality.copy() if source.personality else {},
        system_prompt_prefix=source.system_prompt_prefix,
        greetings=source.greetings.copy() if source.greetings else [],
        thumbnail_url=source.thumbnail_url,
        preview_video_url=source.preview_video_url,
        tags=source.tags.copy() if source.tags else [],
        is_public=False,
        is_system=False,
    )

    db.add(clone)
    await db.flush()

    return clone
