"""Integration Catalog and User Integration models.

DB-driven integration system for third-party tools (Slack, Teams, Outlook, etc.)
that work across both provider-managed and platform-managed assistants.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class IntegrationCatalog(Base):
    """Pre-built integration definitions (Slack, Teams, Outlook, etc.).

    System-level catalog — admins seed these, users browse and enable.
    """

    __tablename__ = "integration_catalog"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="custom", nullable=False)

    # Auth configuration
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False)  # api_key, oauth2, webhook, bearer_token
    auth_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Test connection endpoint
    test_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    test_method: Mapped[str] = mapped_column(String(10), default="GET", nullable=False)
    test_headers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Tool schema (OpenAI function-calling format)
    tool_schemas: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)

    # Setup docs
    setup_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    docs_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Display
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user_integrations: Mapped[list["UserIntegration"]] = relationship(
        "UserIntegration", back_populates="catalog_entry", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<IntegrationCatalog(name={self.name})>"


class UserIntegration(Base):
    """User's enabled integrations with their credentials.

    Links a user to a catalog integration with their API keys/tokens.
    """

    __tablename__ = "user_integrations"
    __table_args__ = (
        UniqueConstraint("user_id", "integration_id", name="uq_user_integration"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Encrypted credentials (encrypted at app layer before storage)
    credentials: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Configuration overrides
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Status
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_tested_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    test_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    catalog_entry: Mapped["IntegrationCatalog"] = relationship(
        "IntegrationCatalog", back_populates="user_integrations", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<UserIntegration(user={self.user_id}, integration={self.integration_id})>"
