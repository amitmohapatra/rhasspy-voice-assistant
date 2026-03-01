"""Response API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from src.schemas.base import BaseSchema


class InputItem(BaseSchema):
    """An input item in a create-response request."""

    type: Literal["message", "function_call_output"] = Field(
        ..., description="Item type: message or function_call_output."
    )
    role: str | None = Field(
        default=None, description="Message role (user/system). Required for type=message."
    )
    content: str | None = Field(
        default=None, description="Message content. Required for type=message."
    )
    call_id: str | None = Field(
        default=None, description="Tool call ID. Required for type=function_call_output."
    )
    output: str | None = Field(
        default=None, description="Tool output. Required for type=function_call_output."
    )


class CreateResponseRequest(BaseSchema):
    """Request body for POST /api/v1/responses."""

    assistant_id: UUID = Field(..., description="Assistant to use.")
    input: list[InputItem] = Field(
        ..., min_length=1, description="Input items (at least one message)."
    )
    previous_response_id: UUID | None = Field(
        default=None, description="Previous response ID for multi-turn chaining."
    )
    conversation_id: UUID | None = Field(
        default=None, description="Existing conversation ID. Created if omitted."
    )
    stream: bool = Field(default=True, description="Stream via SSE.")

    # Per-request overrides (all optional — defaults from assistant)
    model: str | None = Field(default=None, description="Model override.")
    provider: str | None = Field(default=None, description="Provider override.")
    instructions: str | None = Field(default=None, description="System prompt override.")
    temperature: float | None = Field(default=None, description="Temperature override.")
    max_tokens: int | None = Field(default=None, description="Max tokens override.")
    tool_ids: list[str] | None = Field(default=None, description="Tool IDs override.")
    knowledge_base_ids: list[UUID] | None = Field(
        default=None, description="Knowledge base IDs override."
    )
    max_tool_rounds: int = Field(default=10, description="Max server-side tool rounds.")
    metadata: dict = Field(default_factory=dict, description="Arbitrary metadata.")


class ResponseItemSchema(BaseSchema):
    """A single item in a response's output."""

    id: UUID
    item_type: str
    direction: str
    sequence_order: int = 0
    role: str | None = None
    content: str | None = None
    call_id: str | None = None
    function_name: str | None = None
    function_arguments: str | None = None
    function_output: str | None = None
    rag_sources: list[dict] | None = None
    created_at: datetime


class ResponseSchema(BaseSchema):
    """Response object returned by the API."""

    id: UUID
    conversation_id: UUID
    assistant_id: UUID
    previous_response_id: UUID | None = None
    model: str
    provider: str
    status: str
    status_reason: str | None = None
    output: list[ResponseItemSchema] = Field(default_factory=list)
    usage: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_model(cls, response) -> "ResponseSchema":
        """Build from ORM model."""
        return cls(
            id=response.id,
            conversation_id=response.conversation_id,
            assistant_id=response.assistant_id,
            previous_response_id=response.previous_response_id,
            model=response.model,
            provider=response.provider,
            status=response.status,
            status_reason=response.status_reason,
            output=[
                ResponseItemSchema(
                    id=item.id,
                    item_type=item.item_type,
                    direction=item.direction,
                    sequence_order=item.sequence_order,
                    role=item.role,
                    content=item.content,
                    call_id=item.call_id,
                    function_name=item.function_name,
                    function_arguments=item.function_arguments,
                    function_output=item.function_output,
                    rag_sources=item.rag_sources,
                    created_at=item.created_at,
                )
                for item in (response.items or [])
            ],
            usage={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
            },
            metadata=response.response_metadata or {},
            created_at=response.created_at,
        )
