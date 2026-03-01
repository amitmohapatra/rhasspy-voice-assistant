"""Conversation model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.assistant import Assistant
    from src.models.response import Response


class Conversation(Base):
    """Conversation/Thread model — lightweight UI grouping for responses."""

    __tablename__ = "conversations"

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

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Conversation status: active, archived, deleted
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    # Response tracking
    latest_response_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("responses.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    response_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Metadata (source, channel, etc.)
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="conversations")
    assistant: Mapped["Assistant"] = relationship(
        "Assistant", back_populates="conversations"
    )
    responses: Mapped[list["Response"]] = relationship(
        "Response",
        back_populates="conversation",
        foreign_keys="Response.conversation_id",
        lazy="selectin",
        order_by="Response.created_at",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, status={self.status})>"
