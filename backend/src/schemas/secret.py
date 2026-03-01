"""Secret schemas for API key and credential management."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from src.schemas.base import BaseSchema, IDMixin, TimestampMixin


class SecretCreate(BaseSchema):
    """Schema for creating/setting a secret."""

    key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Secret key name (e.g., OPENAI_API_KEY).",
        json_schema_extra={"example": "OPENAI_API_KEY"}
    )
    value: str = Field(
        ...,
        min_length=1,
        description="Secret value (will be encrypted at rest).",
        json_schema_extra={"example": "sk-..."}
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of the secret.",
        json_schema_extra={"example": "OpenAI API key for GPT models"}
    )
    category: str = Field(
        default="custom",
        description="Category: provider, tool, or custom.",
        json_schema_extra={"example": "provider"}
    )
    used_by: str | None = Field(
        default=None,
        description="Which provider/tool uses this secret.",
        json_schema_extra={"example": "openai"}
    )


class SecretUpdate(BaseSchema):
    """Schema for updating a secret."""

    value: str | None = Field(
        default=None,
        min_length=1,
        description="Updated secret value.",
    )
    description: str | None = Field(
        default=None,
        description="Updated description.",
    )


class SecretResponse(BaseSchema, IDMixin, TimestampMixin):
    """Schema for secret metadata in API responses.

    Note: The actual value is NEVER exposed via API.
    """

    project_id: UUID = Field(
        ...,
        description="ID of the project owning this secret.",
    )
    key: str = Field(
        ...,
        description="Secret key name.",
        json_schema_extra={"example": "OPENAI_API_KEY"}
    )
    description: str | None = Field(
        default=None,
        description="Description of the secret.",
    )
    category: str = Field(
        ...,
        description="Category: provider, tool, or custom.",
    )
    used_by: str | None = Field(
        default=None,
        description="Which provider/tool uses this.",
    )
    is_required: bool = Field(
        default=False,
        description="Whether this secret is required.",
    )
    is_set: bool = Field(
        default=False,
        description="Whether a value has been set (not the value itself).",
    )


class SecretListResponse(BaseSchema):
    """Schema for paginated list of secrets."""

    items: list[SecretResponse] = Field(
        default_factory=list,
        description="List of secret metadata.",
    )
    total: int = Field(
        ...,
        description="Total number of secrets.",
    )


class SecretCheckRequest(BaseSchema):
    """Schema for checking which secrets are set."""

    keys: list[str] = Field(
        ...,
        description="List of secret keys to check.",
        json_schema_extra={"example": ["OPENAI_API_KEY", "SLACK_BOT_TOKEN"]}
    )


class SecretCheckResponse(BaseSchema):
    """Response for secret check."""

    results: dict[str, bool] = Field(
        ...,
        description="Map of key -> is_set.",
        json_schema_extra={"example": {"OPENAI_API_KEY": True, "SLACK_BOT_TOKEN": False}}
    )
