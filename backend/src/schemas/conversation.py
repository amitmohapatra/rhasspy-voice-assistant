"""Conversation schemas with comprehensive Swagger documentation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from src.schemas.base import BaseSchema, IDMixin, TimestampMixin
from src.schemas.enums import ConversationStatus


class ConversationCreate(BaseSchema):
    """Schema for creating a new conversation."""

    assistant_id: UUID = Field(
        ...,
        description="ID of the assistant to use for this conversation.",
    )
    title: str | None = Field(
        default=None,
        description="Optional title for the conversation.",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata for the conversation.",
    )


class ConversationUpdate(BaseSchema):
    """Schema for updating a conversation."""

    title: str | None = Field(default=None, description="Updated title.")
    status: ConversationStatus | None = Field(default=None, description="Updated status.")
    metadata: dict | None = Field(default=None, description="Updated metadata.")


class ConversationResponse(BaseSchema, IDMixin, TimestampMixin):
    """Schema for conversation data in API responses."""

    user_id: UUID | None = None
    assistant_id: UUID
    title: str | None = None
    status: ConversationStatus
    latest_response_id: UUID | None = None
    response_count: int = 0
    metadata: dict = Field(default_factory=dict)


class ConversationListResponse(BaseSchema):
    """Schema for paginated list of conversations."""

    items: list[ConversationResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    has_more: bool
