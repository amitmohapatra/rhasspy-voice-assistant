"""Assistant schemas with comprehensive Swagger documentation."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from src.schemas.base import BaseSchema, IDMixin, TimestampMixin
from src.schemas.enums import LLMProvider, OpenAIModel


class AssistantCreate(BaseSchema):
    """Schema for creating a new AI assistant.

    An assistant is a configured AI agent with specific behavior,
    personality, and capabilities defined by its system prompt and settings.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the assistant.",
        json_schema_extra={"example": "Customer Support Agent"}
    )
    description: str | None = Field(
        default=None,
        description="Description of the assistant's purpose and capabilities.",
        json_schema_extra={"example": "A helpful assistant for answering customer questions about our products."}
    )
    provider: LLMProvider = Field(
        default=LLMProvider.OPENAI,
        description="LLM provider to use for this assistant.",
        json_schema_extra={"example": "openai"}
    )
    model: str = Field(
        default="gpt-4o",
        description="Model ID to use. Must be compatible with the selected provider.",
        json_schema_extra={"example": "gpt-4o"}
    )
    system_prompt: str = Field(
        ...,
        min_length=1,
        description="System prompt defining the assistant's behavior and personality.",
        json_schema_extra={
            "example": "You are a helpful customer support agent for Acme Corp. Be friendly, professional, and helpful. Always try to understand the customer's needs before providing a solution."
        }
    )
    temperature: float = Field(
        default=0.7,
        ge=0,
        le=2,
        description="Sampling temperature. Higher values make output more random, lower values more deterministic. Range: 0-2.",
        json_schema_extra={"example": 0.7}
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=128000,
        description="Maximum number of tokens in the response. Range: 1-128000.",
        json_schema_extra={"example": 4096}
    )
    top_p: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Nucleus sampling parameter. Range: 0-1.",
        json_schema_extra={"example": 1.0}
    )
    tools: list[str] = Field(
        default_factory=list,
        description="List of tool IDs that this assistant can use.",
        json_schema_extra={"example": ["web_search", "calculator", "code_interpreter"]}
    )
    knowledge_base_ids: list[UUID] = Field(
        default_factory=list,
        description="List of knowledge base IDs for RAG capabilities.",
        json_schema_extra={"example": ["550e8400-e29b-41d4-a716-446655440000"]}
    )
    settings: dict = Field(
        default_factory=dict,
        description="Additional settings for the assistant.",
        json_schema_extra={
            "example": {
                "response_format": "text",
                "stop_sequences": ["END"],
                "presence_penalty": 0,
                "frequency_penalty": 0
            }
        }
    )
    avatar_enabled: bool = Field(
        default=True,
        description="Whether to enable 3D avatar for this assistant."
    )
    avatar_config: dict = Field(
        default_factory=dict,
        description="Avatar configuration including appearance and animations.",
        json_schema_extra={
            "example": {
                "model": "professional_female",
                "idle_animation": "breathing",
                "talking_animation": "lip_sync"
            }
        }
    )
    voice_enabled: bool = Field(
        default=True,
        description="Whether to enable voice capabilities (STT/TTS)."
    )
    voice_config: dict = Field(
        default_factory=dict,
        description="Voice configuration including TTS and STT settings.",
        json_schema_extra={
            "example": {
                "tts_provider": "elevenlabs",
                "tts_voice_id": "21m00Tcm4TlvDq8ikWAM",
                "stt_provider": "openai",
                "language": "en-US"
            }
        }
    )


class AssistantUpdate(BaseSchema):
    """Schema for updating an existing assistant.

    All fields are optional. Only provided fields will be updated.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Name of the assistant.",
        json_schema_extra={"example": "Customer Support Agent v2"}
    )
    description: str | None = Field(
        default=None,
        description="Description of the assistant's purpose.",
        json_schema_extra={"example": "Updated description for the assistant."}
    )
    system_prompt: str | None = Field(
        default=None,
        description="System prompt defining behavior.",
        json_schema_extra={"example": "You are an updated helpful assistant."}
    )
    temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
        description="Sampling temperature (0-2).",
        json_schema_extra={"example": 0.5}
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        le=128000,
        description="Maximum response tokens.",
        json_schema_extra={"example": 8192}
    )
    top_p: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Nucleus sampling parameter.",
        json_schema_extra={"example": 0.9}
    )
    tools: list[str] | None = Field(
        default=None,
        description="List of enabled tool IDs.",
        json_schema_extra={"example": ["web_search"]}
    )
    knowledge_base_ids: list[UUID] | None = Field(
        default=None,
        description="List of knowledge base IDs.",
        json_schema_extra={"example": []}
    )
    settings: dict | None = Field(
        default=None,
        description="Additional settings.",
        json_schema_extra={"example": {"response_format": "markdown"}}
    )
    avatar_enabled: bool | None = Field(
        default=None,
        description="Enable/disable avatar."
    )
    avatar_config: dict | None = Field(
        default=None,
        description="Avatar configuration."
    )
    voice_enabled: bool | None = Field(
        default=None,
        description="Enable/disable voice."
    )
    voice_config: dict | None = Field(
        default=None,
        description="Voice configuration."
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the assistant is active and available."
    )
    is_public: bool | None = Field(
        default=None,
        description="Whether the assistant is publicly accessible."
    )


class AssistantResponse(BaseSchema, IDMixin, TimestampMixin):
    """Schema for assistant data in API responses.

    Contains complete assistant configuration and metadata.
    """

    name: str = Field(
        ...,
        description="Name of the assistant.",
        json_schema_extra={"example": "Customer Support Agent"}
    )
    description: str | None = Field(
        default=None,
        description="Description of the assistant.",
        json_schema_extra={"example": "A helpful assistant for customer support."}
    )
    provider: LLMProvider = Field(
        ...,
        description="LLM provider.",
        json_schema_extra={"example": "openai"}
    )
    model: str = Field(
        ...,
        description="Model ID.",
        json_schema_extra={"example": "gpt-4o"}
    )
    system_prompt: str = Field(
        ...,
        description="System prompt.",
        json_schema_extra={"example": "You are a helpful assistant."}
    )
    temperature: float = Field(
        ...,
        description="Sampling temperature.",
        json_schema_extra={"example": 0.7}
    )
    max_tokens: int = Field(
        ...,
        description="Maximum tokens.",
        json_schema_extra={"example": 4096}
    )
    top_p: float = Field(
        ...,
        description="Top-p sampling.",
        json_schema_extra={"example": 1.0}
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Enabled tools.",
        json_schema_extra={"example": ["web_search"]}
    )
    knowledge_base_ids: list[UUID] = Field(
        default_factory=list,
        description="Knowledge base IDs.",
        json_schema_extra={"example": []}
    )
    settings: dict = Field(
        default_factory=dict,
        description="Additional settings.",
        json_schema_extra={"example": {}}
    )
    avatar_enabled: bool = Field(
        ...,
        description="Avatar enabled.",
        json_schema_extra={"example": True}
    )
    avatar_config: dict = Field(
        default_factory=dict,
        description="Avatar configuration.",
        json_schema_extra={"example": {}}
    )
    voice_enabled: bool = Field(
        ...,
        description="Voice enabled.",
        json_schema_extra={"example": True}
    )
    voice_config: dict = Field(
        default_factory=dict,
        description="Voice configuration.",
        json_schema_extra={"example": {}}
    )
    is_active: bool = Field(
        ...,
        description="Whether active.",
        json_schema_extra={"example": True}
    )
    is_public: bool = Field(
        ...,
        description="Whether public.",
        json_schema_extra={"example": False}
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Customer Support Agent",
                "description": "A helpful assistant for customer support.",
                "provider": "openai",
                "model": "gpt-4o",
                "system_prompt": "You are a helpful customer support assistant.",
                "temperature": 0.7,
                "max_tokens": 4096,
                "top_p": 1.0,
                "tools": ["web_search"],
                "knowledge_base_ids": [],
                "settings": {},
                "avatar_enabled": True,
                "avatar_config": {"model": "professional_female"},
                "voice_enabled": True,
                "voice_config": {"tts_provider": "elevenlabs"},
                "is_active": True,
                "is_public": False,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }
    }


class AssistantListResponse(BaseSchema):
    """Schema for paginated list of assistants."""

    items: list[AssistantResponse] = Field(
        default_factory=list,
        description="List of assistants."
    )
    total: int = Field(
        ...,
        description="Total number of assistants.",
        json_schema_extra={"example": 10}
    )
    page: int = Field(
        ...,
        description="Current page number.",
        json_schema_extra={"example": 1}
    )
    page_size: int = Field(
        ...,
        description="Number of items per page.",
        json_schema_extra={"example": 20}
    )
    has_more: bool = Field(
        ...,
        description="Whether there are more pages.",
        json_schema_extra={"example": False}
    )
