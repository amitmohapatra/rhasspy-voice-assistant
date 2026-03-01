"""Voice preset model for storing user TTS/STT configurations."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class VoicePreset(Base):
    """Voice preset model.

    Stores user-created TTS and STT presets with provider-specific configuration.
    """

    __tablename__ = "voice_presets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # "tts" or "stt"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", backref="voice_presets")

    def __repr__(self) -> str:
        return f"<VoicePreset(id={self.id}, name={self.name}, type={self.type})>"
