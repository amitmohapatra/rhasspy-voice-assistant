"""Integration catalog and user integration schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IntegrationCatalogResponse(BaseModel):
    """Integration catalog entry response."""

    id: str
    name: str
    display_name: str
    description: str | None = None
    icon: str | None = None
    category: str
    auth_type: str
    auth_schema: dict
    test_endpoint: str | None = None
    tool_schemas: list[dict] = []
    setup_instructions: str | None = None
    docs_url: str | None = None
    sort_order: int = 0
    is_active: bool = True
    is_featured: bool = False
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class IntegrationCatalogCreate(BaseModel):
    """Create a new integration catalog entry."""

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    icon: str | None = None
    category: str = "custom"
    auth_type: str = "api_key"
    auth_schema: dict = Field(default_factory=dict)
    test_endpoint: str | None = None
    test_method: str = "GET"
    test_headers: dict = Field(default_factory=dict)
    tool_schemas: list[dict] = Field(default_factory=list)
    setup_instructions: str | None = None
    docs_url: str | None = None
    sort_order: int = 0
    is_featured: bool = False


class UserIntegrationResponse(BaseModel):
    """User integration response (credentials redacted)."""

    id: str
    integration_id: str
    is_verified: bool
    is_enabled: bool
    config: dict = {}
    last_tested_at: str | None = None
    test_error: str | None = None
    created_at: str
    updated_at: str
    # Joined catalog info
    catalog: IntegrationCatalogResponse | None = None

    model_config = {"from_attributes": True}


class UserIntegrationCreate(BaseModel):
    """Enable an integration for a user."""

    integration_id: str
    credentials: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)


class UserIntegrationUpdate(BaseModel):
    """Update integration credentials or config."""

    credentials: dict | None = None
    config: dict | None = None
    is_enabled: bool | None = None


class IntegrationTestRequest(BaseModel):
    """Test integration connection."""

    integration_id: str
    credentials: dict = Field(default_factory=dict)


class IntegrationTestResponse(BaseModel):
    """Test result."""

    success: bool
    message: str = ""
    status_code: int | None = None
    duration_ms: float | None = None
