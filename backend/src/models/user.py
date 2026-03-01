"""User model for authentication and authorization."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.conversation import Conversation


class User(Base):
    """User model.

    Every authenticated user has full access -- there are no role distinctions.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # User preferences and settings
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Account status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Timestamps
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user", lazy="select"
    )

    @property
    def name(self) -> str:
        """Backwards compatibility for name field."""
        return self.full_name or ""

    @property
    def password_hash(self) -> str:
        """Backwards compatibility for password_hash field."""
        return self.hashed_password

    @password_hash.setter
    def password_hash(self, value: str) -> None:
        """Backwards compatibility for password_hash field."""
        self.hashed_password = value

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
