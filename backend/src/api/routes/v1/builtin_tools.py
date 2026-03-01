"""Built-in Tools API - Manage vendor-provided tools via database.

All built-in tools are database-driven. Authenticated users can:
- Add new built-in tools for any vendor
- Edit tool configurations, descriptions, schemas
- Enable/disable tools
- Set model-specific overrides
- Import/export tool configurations

NO CODE CHANGES REQUIRED to add/modify built-in tools.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.builtin_tool import ToolCategory
from src.models.capability import CapabilityType
from src.services.builtin_tool_service import BuiltinToolService


router = APIRouter(prefix="/builtin-tools", tags=["Built-in Tools"])


# ==================== Schemas ====================

class CreateBuiltinToolRequest(BaseModel):
    """Request to create a built-in tool."""
    provider_id: str
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    capability_type: str
    description: str | None = None
    icon: str | None = None
    category: str = "tools"
    config_schema: dict = Field(default_factory=dict)
    default_config: dict = Field(default_factory=dict)
    api_config: dict = Field(default_factory=dict)
    is_preview: bool = False
    is_beta: bool = False
    is_always_on: bool = False
    supported_model_patterns: list[str] = Field(default_factory=list)
    excluded_model_patterns: list[str] = Field(default_factory=list)
    docs_url: str | None = None
    sort_order: int = 0


class UpdateBuiltinToolRequest(BaseModel):
    """Request to update a built-in tool."""
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    category: str | None = None
    config_schema: dict | None = None
    default_config: dict | None = None
    api_config: dict | None = None
    is_active: bool | None = None
    is_preview: bool | None = None
    is_beta: bool | None = None
    is_deprecated: bool | None = None
    is_always_on: bool | None = None
    supported_model_patterns: list[str] | None = None
    excluded_model_patterns: list[str] | None = None
    docs_url: str | None = None
    examples: dict | None = None
    sort_order: int | None = None


class BuiltinToolResponse(BaseModel):
    """Built-in tool response."""
    id: str
    provider_id: str
    name: str
    display_name: str
    description: str | None
    icon: str | None
    category: str | None
    capability_type: str
    config_schema: dict
    default_config: dict
    api_config: dict
    is_builtin: bool = True
    is_active: bool
    is_preview: bool
    is_beta: bool
    is_deprecated: bool
    is_always_on: bool
    supported_model_patterns: list[str]
    excluded_model_patterns: list[str]
    docs_url: str | None
    sort_order: int

    class Config:
        from_attributes = True


class CreateModelOverrideRequest(BaseModel):
    """Request to create a model override."""
    builtin_tool_id: str
    model_pattern: str
    is_enabled: bool = True
    config_overrides: dict = Field(default_factory=dict)
    api_config_overrides: dict = Field(default_factory=dict)


class ImportToolsRequest(BaseModel):
    """Request to import tools for a provider."""
    provider_id: str
    tools: list[dict]
    replace_existing: bool = False


# ==================== Endpoints ====================

@router.get(
    "",
    response_model=list[BuiltinToolResponse],
    summary="List all built-in tools",
)
async def list_builtin_tools(
    provider_id: str | None = None,
    capability_type: str | None = None,
    category: str | None = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all built-in tools with optional filters.

    Available to all authenticated users.
    """
    service = BuiltinToolService(db)

    cap_type = None
    if capability_type:
        try:
            cap_type = CapabilityType(capability_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid capability type: {capability_type}",
            )

    cat = None
    if category:
        try:
            cat = ToolCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category: {category}",
            )

    tools = await service.list_builtin_tools(
        provider_id=UUID(provider_id) if provider_id else None,
        capability_type=cap_type,
        category=cat,
        include_inactive=include_inactive,
    )

    return [t.to_dict() for t in tools]


@router.get(
    "/provider/{provider_id}",
    response_model=list[BuiltinToolResponse],
    summary="Get tools by provider",
)
async def get_tools_by_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all built-in tools for a specific provider."""
    service = BuiltinToolService(db)
    tools = await service.get_tools_by_provider(provider_id)
    return [t.to_dict() for t in tools]


@router.get(
    "/provider/name/{provider_name}",
    response_model=list[BuiltinToolResponse],
    summary="Get tools by provider name",
)
async def get_tools_by_provider_name(
    provider_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all built-in tools by provider name (e.g., 'openai', 'anthropic')."""
    service = BuiltinToolService(db)
    tools = await service.get_tools_by_provider_name(provider_name.lower())
    return [t.to_dict() for t in tools]


@router.get(
    "/model/{model_id}",
    summary="Get available tools for model",
)
async def get_tools_for_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all built-in tools available for a specific model.

    This is called during assistant creation to show which
    vendor tools the selected model supports.
    """
    service = BuiltinToolService(db)
    tools = await service.get_available_tools_for_model(model_id)
    return {"model_id": str(model_id), "tools": tools, "total": len(tools)}


@router.get(
    "/{tool_id}",
    response_model=BuiltinToolResponse,
    summary="Get built-in tool by ID",
)
async def get_builtin_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific built-in tool by ID."""
    service = BuiltinToolService(db)
    tool = await service.get_builtin_tool(tool_id)

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Built-in tool {tool_id} not found",
        )

    return tool.to_dict()


@router.post(
    "",
    response_model=BuiltinToolResponse,
    summary="Create built-in tool",
    dependencies=[Depends(get_current_user)],
)
async def create_builtin_tool(
    request: CreateBuiltinToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new built-in tool.

    This allows adding new vendor tools without code changes.
    """
    try:
        cap_type = CapabilityType(request.capability_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid capability type: {request.capability_type}",
        )

    try:
        category = ToolCategory(request.category)
    except ValueError:
        category = ToolCategory.TOOLS

    service = BuiltinToolService(db)
    tool = await service.create_builtin_tool(
        provider_id=UUID(request.provider_id),
        name=request.name,
        display_name=request.display_name,
        capability_type=cap_type,
        description=request.description,
        icon=request.icon,
        category=category,
        config_schema=request.config_schema,
        default_config=request.default_config,
        api_config=request.api_config,
        is_preview=request.is_preview,
        is_beta=request.is_beta,
        is_always_on=request.is_always_on,
        supported_model_patterns=request.supported_model_patterns,
        excluded_model_patterns=request.excluded_model_patterns,
        docs_url=request.docs_url,
        sort_order=request.sort_order,
    )

    return tool.to_dict()


@router.put(
    "/{tool_id}",
    response_model=BuiltinToolResponse,
    summary="Update built-in tool",
    dependencies=[Depends(get_current_user)],
)
async def update_builtin_tool(
    tool_id: UUID,
    request: UpdateBuiltinToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a built-in tool."""
    service = BuiltinToolService(db)

    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    if "category" in updates:
        try:
            updates["category"] = ToolCategory(updates["category"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category: {updates['category']}",
            )

    try:
        tool = await service.update_builtin_tool(tool_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return tool.to_dict()


@router.delete(
    "/{tool_id}",
    summary="Delete built-in tool",
    dependencies=[Depends(get_current_user)],
)
async def delete_builtin_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a built-in tool."""
    service = BuiltinToolService(db)
    deleted = await service.delete_builtin_tool(tool_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Built-in tool {tool_id} not found",
        )

    return {"message": "Tool deleted successfully"}


@router.post(
    "/import",
    summary="Import tools for provider",
    dependencies=[Depends(get_current_user)],
)
async def import_tools(
    request: ImportToolsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import multiple tools for a provider.

    Allows bulk import of tool configurations from JSON.
    """
    service = BuiltinToolService(db)
    result = await service.import_tools_for_provider(
        provider_id=UUID(request.provider_id),
        tools_config=request.tools,
        replace_existing=request.replace_existing,
    )
    return result


@router.get(
    "/export/{provider_id}",
    summary="Export tools for provider",
    dependencies=[Depends(get_current_user)],
)
async def export_tools(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Export all tools for a provider as JSON.

    Useful for backup or copying tools between environments.
    """
    service = BuiltinToolService(db)
    tools = await service.get_tools_by_provider(provider_id)

    return {
        "provider_id": str(provider_id),
        "tools": [t.to_dict() for t in tools],
        "total": len(tools),
    }


# ==================== Model Overrides (DEPRECATED — use /model-tool-support) ====================

@router.post(
    "/overrides",
    summary="Create model override (DEPRECATED)",
    dependencies=[Depends(get_current_user)],
    deprecated=True,
)
async def create_model_override(
    request: CreateModelOverrideRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a model-specific override for a built-in tool.

    Allows customizing tool behavior for specific models.
    """
    service = BuiltinToolService(db)
    override = await service.create_model_override(
        builtin_tool_id=UUID(request.builtin_tool_id),
        model_pattern=request.model_pattern,
        is_enabled=request.is_enabled,
        config_overrides=request.config_overrides,
        api_config_overrides=request.api_config_overrides,
    )

    return {
        "id": override.id,
        "builtin_tool_id": override.builtin_tool_id,
        "model_pattern": override.model_pattern,
        "is_enabled": override.is_enabled,
        "config_overrides": override.config_overrides,
    }


@router.delete(
    "/overrides/{override_id}",
    summary="Delete model override (DEPRECATED)",
    dependencies=[Depends(get_current_user)],
    deprecated=True,
)
async def delete_model_override(
    override_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a model override."""
    service = BuiltinToolService(db)
    deleted = await service.delete_model_override(override_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Override {override_id} not found",
        )

    return {"message": "Override deleted successfully"}


# ==================== Capability Types Reference ====================

@router.get(
    "/reference/capability-types",
    summary="List capability types",
)
async def list_capability_types():
    """List all available capability types for built-in tools."""
    return {
        "capability_types": [
            {"value": cap.value, "name": cap.name}
            for cap in CapabilityType
        ]
    }


@router.get(
    "/reference/categories",
    summary="List tool categories",
)
async def list_categories():
    """List all available tool categories."""
    return {
        "categories": [
            {"value": cat.value, "name": cat.name}
            for cat in ToolCategory
        ]
    }
