"""Built-in Tool Database Models - Fully database-driven vendor tools."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.capability import CapabilityType

if TYPE_CHECKING:
    from src.models.ai_model import AIProvider
    from src.models.model_tool_support import ModelToolSupport


class ToolCategory(str, Enum):
    """Tool categories for organization."""
    RETRIEVAL = "retrieval"
    EXECUTION = "execution"
    GENERATION = "generation"
    AUTOMATION = "automation"
    OUTPUT = "output"
    INTEGRATION = "integration"
    REASONING = "reasoning"
    TOOLS = "tools"


class BuiltinTool(Base):
    """Vendor-provided built-in tools."""

    __tablename__ = "builtin_tools"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_providers.id"), nullable=False
    )
    capability_type: Mapped[str] = mapped_column(
        SQLEnum(CapabilityType), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(
        SQLEnum(ToolCategory), default=ToolCategory.TOOLS
    )
    config_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    default_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    api_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_preview: Mapped[bool] = mapped_column(Boolean, default=False)
    is_beta: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_always_on: Mapped[bool] = mapped_column(Boolean, default=False)
    supported_model_patterns: Mapped[dict] = mapped_column(JSONB, default=list)
    excluded_model_patterns: Mapped[dict] = mapped_column(JSONB, default=list)
    docs_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    examples: Mapped[dict] = mapped_column(JSONB, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    provider: Mapped["AIProvider"] = relationship("AIProvider", back_populates="builtin_tools")
    model_support_entries: Mapped[list["ModelToolSupport"]] = relationship(
        "ModelToolSupport",
        back_populates="builtin_tool",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("provider_id", "name", name="uq_provider_builtin_tool"),
        Index("idx_builtin_tools_provider", "provider_id"),
        Index("idx_builtin_tools_capability", "capability_type"),
        Index("idx_builtin_tools_active", "is_active"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "provider_id": str(self.provider_id),
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category.value if self.category else None,
            "capability_type": self.capability_type.value if self.capability_type else None,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "api_config": self.api_config,
            "is_builtin": True,
            "is_active": self.is_active,
            "is_preview": self.is_preview,
            "is_beta": self.is_beta,
            "is_deprecated": self.is_deprecated,
            "is_always_on": self.is_always_on,
            "supported_model_patterns": self.supported_model_patterns,
            "excluded_model_patterns": self.excluded_model_patterns,
            "docs_url": self.docs_url,
            "sort_order": self.sort_order,
        }


class BuiltinToolModelOverride(Base):
    """Model-specific overrides for built-in tools."""

    __tablename__ = "builtin_tool_model_overrides"

    builtin_tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builtin_tools.id", ondelete="CASCADE"), nullable=False
    )
    model_pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)
    api_config_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    builtin_tool: Mapped["BuiltinTool"] = relationship("BuiltinTool")

    __table_args__ = (
        UniqueConstraint("builtin_tool_id", "model_pattern", name="uq_builtin_tool_model_override"),
    )
