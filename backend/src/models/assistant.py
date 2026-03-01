"""Assistant model - AI assistant configuration."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.conversation import Conversation
    from src.models.project import Project
    from src.models.user import User


class Assistant(Base):
    """AI Assistant configuration model."""

    __tablename__ = "assistants"

    # Owner — each user sees only their own assistants
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional project association
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # LLM Configuration
    provider: Mapped[str] = mapped_column(
        String(50), default="openai", nullable=False
    )  # openai, anthropic, google, bedrock, custom
    model: Mapped[str] = mapped_column(String(100), default="gpt-4o", nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Model parameters
    temperature: Mapped[float] = mapped_column(
        Numeric(3, 2), default=0.7, nullable=False
    )
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    top_p: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0, nullable=False)

    # Tool references: builtin tool names (e.g. "file_search") and custom tool UUIDs
    tool_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )

    # Knowledge base IDs (references to KnowledgeBase.id)
    knowledge_base_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, nullable=False
    )

    # Provider configurations for this assistant
    provider_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Additional settings
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Avatar configuration
    avatar_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    avatar_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Voice configuration
    voice_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    voice_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Welcome message for conversations
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Conversation starters (suggested prompts)
    conversation_starters: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="selectin",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="assistant", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    @property
    def tools(self) -> list[str]:
        """Return tool references for API compatibility."""
        return list(self.tool_ids)

    def __repr__(self) -> str:
        return f"<Assistant(id={self.id}, name={self.name}, model={self.model})>"
