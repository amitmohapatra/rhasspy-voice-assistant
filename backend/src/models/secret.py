"""Secret model - Environment variables and API keys management."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.project import Project


class Secret(Base):
    """Secret/Environment variable model.

    Stores encrypted secrets that can be referenced by tools and providers.
    Values are encrypted at rest and only decrypted when needed.
    """

    __tablename__ = "secrets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Secret key name (e.g., OPENAI_API_KEY, SLACK_TOKEN)
    key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Encrypted value
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Human-readable description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Category for organization: provider, tool, custom
    category: Mapped[str] = mapped_column(String(50), default="custom", nullable=False)

    # Which provider/tool uses this secret
    used_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Is this required for the associated provider/tool?
    is_required: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Has value been set?
    is_set: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="secrets")

    def __repr__(self) -> str:
        return f"<Secret(id={self.id}, key={self.key}, is_set={self.is_set})>"


# Predefined secrets that providers need
PROVIDER_SECRETS = {
    "openai": {
        "key": "OPENAI_API_KEY",
        "description": "OpenAI API key for GPT models, Whisper, TTS, and embeddings",
        "category": "provider",
        "is_required": True,
    },
    "anthropic": {
        "key": "ANTHROPIC_API_KEY",
        "description": "Anthropic API key for Claude models",
        "category": "provider",
        "is_required": True,
    },
    "google": {
        "key": "GOOGLE_API_KEY",
        "description": "Google AI API key for Gemini models",
        "category": "provider",
        "is_required": True,
    },
    "google_cloud": {
        "key": "GOOGLE_APPLICATION_CREDENTIALS",
        "description": "Path to Google Cloud service account JSON file",
        "category": "provider",
        "is_required": True,
    },
    "azure": {
        "key": "AZURE_SPEECH_KEY",
        "description": "Azure Speech Services subscription key",
        "category": "provider",
        "is_required": True,
    },
    "azure_region": {
        "key": "AZURE_SPEECH_REGION",
        "description": "Azure Speech Services region (e.g., eastus)",
        "category": "provider",
        "is_required": True,
    },
    "elevenlabs": {
        "key": "ELEVENLABS_API_KEY",
        "description": "ElevenLabs API key for voice synthesis",
        "category": "provider",
        "is_required": True,
    },
    "deepgram": {
        "key": "DEEPGRAM_API_KEY",
        "description": "Deepgram API key for speech-to-text",
        "category": "provider",
        "is_required": True,
    },
    "assemblyai": {
        "key": "ASSEMBLYAI_API_KEY",
        "description": "AssemblyAI API key for transcription",
        "category": "provider",
        "is_required": True,
    },
    "cohere": {
        "key": "COHERE_API_KEY",
        "description": "Cohere API key for embeddings",
        "category": "provider",
        "is_required": True,
    },
    "voyage": {
        "key": "VOYAGE_API_KEY",
        "description": "Voyage AI API key for embeddings",
        "category": "provider",
        "is_required": True,
    },
    "qdrant": {
        "key": "QDRANT_API_KEY",
        "description": "Qdrant API key for vector database",
        "category": "provider",
        "is_required": False,
    },
    "playht": {
        "key": "PLAYHT_API_KEY",
        "description": "PlayHT API key for voice synthesis",
        "category": "provider",
        "is_required": True,
    },
    "playht_user": {
        "key": "PLAYHT_USER_ID",
        "description": "PlayHT User ID",
        "category": "provider",
        "is_required": True,
    },
}

TOOL_SECRETS = {
    "slack": {
        "key": "SLACK_BOT_TOKEN",
        "description": "Slack Bot OAuth token (xoxb-...)",
        "category": "tool",
        "is_required": True,
    },
    "github": {
        "key": "GITHUB_TOKEN",
        "description": "GitHub personal access token",
        "category": "tool",
        "is_required": True,
    },
    "jira": {
        "key": "JIRA_API_TOKEN",
        "description": "Jira API token",
        "category": "tool",
        "is_required": True,
    },
    "notion": {
        "key": "NOTION_API_KEY",
        "description": "Notion integration token",
        "category": "tool",
        "is_required": True,
    },
    "linear": {
        "key": "LINEAR_API_KEY",
        "description": "Linear API key",
        "category": "tool",
        "is_required": True,
    },
    "sendgrid": {
        "key": "SENDGRID_API_KEY",
        "description": "SendGrid API key for email",
        "category": "tool",
        "is_required": True,
    },
    "twilio_sid": {
        "key": "TWILIO_ACCOUNT_SID",
        "description": "Twilio Account SID",
        "category": "tool",
        "is_required": True,
    },
    "twilio_token": {
        "key": "TWILIO_AUTH_TOKEN",
        "description": "Twilio Auth Token",
        "category": "tool",
        "is_required": True,
    },
}
