"""API Key model for external integrations."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class APIKey(Base):
    """API Key for external access."""

    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hashed key (the actual key is only shown once on creation)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Key prefix for identification (e.g., "sk-...")
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)

    # Permissions: full, read, write
    permissions: Mapped[str] = mapped_column(String(50), default="full", nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Expiration
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Last used
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.key_prefix})>"
