"""Usage tracking model for analytics and billing."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class UsageLog(Base):
    """Usage log for token tracking and billing."""

    __tablename__ = "usage_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assistants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # LLM details
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Token usage
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cost (in USD)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0"), nullable=False
    )

    # Performance
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Response ID (for Responses API)
    response_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("responses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Request type: chat, embedding, tts, stt
    request_type: Mapped[str] = mapped_column(
        String(50), default="chat", nullable=False
    )

    def __repr__(self) -> str:
        return f"<UsageLog(id={self.id}, provider={self.provider}, tokens={self.total_tokens})>"
