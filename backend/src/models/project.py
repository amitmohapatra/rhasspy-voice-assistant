"""Project model - Workspace for grouping assistants, KBs, and tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.secret import Secret


class Project(Base):
    """Project/Workspace model for organizing resources."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)  # emoji or icon name
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)  # hex color

    # Provider configuration for this project
    provider_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Project settings
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    secrets: Mapped[list["Secret"]] = relationship(
        "Secret", back_populates="project", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"
