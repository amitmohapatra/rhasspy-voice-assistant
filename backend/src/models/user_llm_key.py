"""User LLM API Key model — encrypted storage of per-user vendor keys."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.user import User


class UserLLMKey(Base):
    """Stores encrypted LLM vendor API keys per user.

    Each user can have one key per provider (e.g., openai, anthropic).
    Keys are encrypted at rest using Fernet (AES-128-CBC).
    """

    __tablename__ = "user_llm_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_llm_key_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    owner: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<UserLLMKey(user_id={self.user_id}, provider={self.provider})>"
