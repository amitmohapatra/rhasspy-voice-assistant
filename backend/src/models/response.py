"""Response and ResponseItem models for the Responses API."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.assistant import Assistant
    from src.models.conversation import Conversation


class Response(Base):
    """A single API response in a conversation chain.

    Each call to POST /api/v1/responses creates one Response.
    Responses are chained via previous_response_id for multi-turn context.
    """

    __tablename__ = "responses"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_response_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("responses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Config snapshot (at time of request)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_ids: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    knowledge_base_ids: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    max_tool_rounds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default="in_progress", nullable=False
    )
    status_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Aggregated usage (across all LLM rounds)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Error (if status=failed)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Arbitrary metadata
    response_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )

    # Relationships
    items: Mapped[list["ResponseItem"]] = relationship(
        "ResponseItem",
        back_populates="response",
        lazy="selectin",
        order_by="ResponseItem.sequence_order",
        cascade="all, delete-orphan",
    )
    assistant: Mapped["Assistant"] = relationship("Assistant", lazy="selectin")
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="responses", foreign_keys=[conversation_id]
    )
    previous_response: Mapped["Response | None"] = relationship(
        "Response", remote_side="Response.id", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Response(id={self.id}, status={self.status})>"


class ResponseItem(Base):
    """A single item within a response (message, function_call, etc.)."""

    __tablename__ = "response_items"

    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Type & direction
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)

    # Message fields (item_type = 'message')
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(50), default="text", nullable=False
    )

    # Function call fields (item_type = 'function_call')
    call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    function_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    function_arguments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Function output fields (item_type = 'function_call_output')
    function_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # RAG context fields (item_type = 'rag_context')
    rag_sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Metadata
    item_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )

    # Relationships
    response: Mapped["Response"] = relationship("Response", back_populates="items")

    def __repr__(self) -> str:
        return f"<ResponseItem(id={self.id}, type={self.item_type}, direction={self.direction})>"
