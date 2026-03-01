"""Voice preset schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from src.schemas.base import BaseSchema, IDMixin, TimestampMixin


class VoicePresetCreate(BaseSchema):
    """Schema for creating a voice preset."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name for this preset.",
        json_schema_extra={"example": "Professional Nova"},
    )
    type: Literal["tts", "stt"] = Field(
        ...,
        description="Preset type: 'tts' for text-to-speech, 'stt' for speech-to-text.",
    )
    config: dict = Field(
        default_factory=dict,
        description="Provider-specific configuration.",
        json_schema_extra={
            "example": {"source": "openai", "voice_id": "nova", "speed": 1.0}
        },
    )
    is_default: bool = Field(
        default=False,
        description="Set as default preset for this type.",
    )


class VoicePresetUpdate(BaseSchema):
    """Schema for updating a voice preset."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: dict | None = None
    is_default: bool | None = None


class VoicePresetResponse(IDMixin, TimestampMixin, BaseSchema):
    """Schema for voice preset response."""

    name: str
    type: str
    config: dict
    is_default: bool


class VoicePresetListResponse(BaseSchema):
    """Paginated list of voice presets."""

    items: list[VoicePresetResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
