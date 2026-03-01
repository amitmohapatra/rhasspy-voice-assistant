"""Model-Tool Support join table — explicit FK-based model/tool compatibility.

Replaces fragile fnmatch glob pattern matching with proper database
relationships between AIModel and BuiltinTool.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class ModelToolSupport(Base):
    """Explicit model-tool compatibility mapping.

    Each row records whether a specific AI model supports a specific
    built-in tool, along with any config overrides for that pair.
    """

    __tablename__ = "model_tool_support"

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    builtin_tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("builtin_tools.id", ondelete="CASCADE"),
        nullable=False,
    )

    is_supported: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    config_overrides: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    api_config_overrides: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Where this mapping came from
    source: Mapped[str] = mapped_column(
        String(50), default="seed", nullable=False
    )  # seed | api | auto

    # Relationships
    model: Mapped["AIModel"] = relationship(
        "AIModel", back_populates="tool_support_entries"
    )
    builtin_tool: Mapped["BuiltinTool"] = relationship(
        "BuiltinTool", back_populates="model_support_entries"
    )

    __table_args__ = (
        UniqueConstraint("model_id", "builtin_tool_id", name="uq_model_tool_support"),
        Index("ix_model_tool_support_model", "model_id"),
        Index("ix_model_tool_support_tool", "builtin_tool_id"),
        Index("ix_model_tool_support_model_supported", "model_id", "is_supported"),
    )

    def __repr__(self) -> str:
        return (
            f"<ModelToolSupport(model={self.model_id}, "
            f"tool={self.builtin_tool_id}, supported={self.is_supported})>"
        )
