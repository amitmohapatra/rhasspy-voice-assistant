"""Tool and ToolExecution models."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.capability import ToolCapabilityRequirement
    from src.models.user import User


class Tool(Base):
    """Tool configuration model.

    Supports multiple tool types:
    - builtin: Pre-configured tools (web_search, calculator, etc.)
    - custom: User-defined tools with custom code/API
    - mcp: Model Context Protocol servers
    - integration: Third-party integrations (Slack, GitHub, etc.)
    """

    __tablename__ = "tools"

    # Owner — each user sees only their own custom tools
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Tool type: builtin, custom, mcp, integration
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Tool category for grouping in UI
    category: Mapped[str] = mapped_column(
        String(50), default="general", nullable=False
    )  # productivity, communication, development, data, custom

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Function calling schema (OpenAI format)
    schema_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Tool implementation config
    implementation: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Required secrets (references to Secret.key)
    required_secrets: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )

    # MCP server configuration (if type=mcp)
    mcp_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Integration config (OAuth, API endpoints)
    integration_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Whether this is a system-provided tool or user-created
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="selectin",
    )
    executions: Mapped[list["ToolExecution"]] = relationship(
        "ToolExecution",
        back_populates="tool",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    capability_requirements: Mapped[list["ToolCapabilityRequirement"]] = relationship(
        "ToolCapabilityRequirement",
        foreign_keys="ToolCapabilityRequirement.tool_id",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, name={self.name}, type={self.type})>"


class ToolExecution(Base):
    """Tool execution log for audit trail."""

    __tablename__ = "tool_executions"

    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    response_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("response_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Execution details
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Status: pending, success, failed
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Performance metrics
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    tool: Mapped["Tool"] = relationship("Tool", back_populates="executions")

    def __repr__(self) -> str:
        return f"<ToolExecution(id={self.id}, status={self.status})>"
