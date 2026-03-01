"""Assistant Tools API - Get available tools for assistant creation.

This endpoint is called when users create/edit assistants to show
which tools are available for the selected model.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.services.assistant_tools_service import AssistantToolsService


router = APIRouter(prefix="/assistant-tools", tags=["Assistant Tools"])


# ==================== Schemas ====================

class BuiltinToolResponse(BaseModel):
    """Built-in tool information."""
    id: str
    name: str
    display_name: str
    description: str
    icon: str | None
    category: str
    capability_type: str
    is_builtin: bool = True
    is_available: bool
    is_preview: bool = False
    is_beta: bool = False
    vendor: str
    config_schema: dict = Field(default_factory=dict)
    default_config: dict = Field(default_factory=dict)


class CustomToolResponse(BaseModel):
    """Custom tool information."""
    id: str
    name: str
    display_name: str
    description: str | None
    icon: str | None
    category: str | None
    type: str
    is_builtin: bool = False
    is_available: bool
    required_capabilities: list[str]
    missing_capabilities: list[str] | None = None
    unavailable_reason: str | None = None
    schema_definition: dict | None = None


class ModelCapabilityInfo(BaseModel):
    """Model capability information."""
    type: str
    is_enabled: bool
    config: dict = Field(default_factory=dict)


class AvailableToolsResponse(BaseModel):
    """Response with all available tools for a model."""
    model_id: str
    model_name: str
    vendor: str
    builtin_tools: list[dict]
    custom_tools: list[dict]
    model_capabilities: list[ModelCapabilityInfo]
    total_available_tools: int


class ValidateToolsRequest(BaseModel):
    """Request to validate tool selection."""
    model_id: str
    builtin_tool_names: list[str] = Field(default_factory=list)
    custom_tool_ids: list[str] = Field(default_factory=list)


class ValidationErrorDetail(BaseModel):
    """Validation error detail."""
    tool: str
    type: str
    error: str


class ValidateToolsResponse(BaseModel):
    """Response from tool validation."""
    valid: bool
    errors: list[ValidationErrorDetail] = Field(default_factory=list)
    validated_builtin_tools: list[str]
    validated_custom_tools: list[str]


# ==================== Endpoints ====================

@router.get(
    "/available/{model_id}",
    response_model=AvailableToolsResponse,
    summary="Get available tools for model",
)
async def get_available_tools(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all available tools for a specific model.

    This endpoint is called when a user selects a model during
    assistant creation. It returns:

    - **builtin_tools**: Vendor-provided tools (file_search, code_interpreter, etc.)
      that the model supports
    - **custom_tools**: User-created function tools that are compatible
      with the model's capabilities
    - **model_capabilities**: List of capabilities the model supports

    Tools are filtered based on the model's capabilities. For example:
    - GPT-4o will show file_search, code_interpreter, web_search
    - o1 (reasoning) won't show file_search (not supported)
    - Custom tools requiring 'vision' won't show for non-vision models

    Example response:
    ```json
    {
      "model_id": "...",
      "model_name": "GPT-4o",
      "vendor": "openai",
      "builtin_tools": [
        {
          "id": "builtin_openai_file_search",
          "name": "file_search",
          "display_name": "File Search",
          "is_available": true,
          ...
        }
      ],
      "custom_tools": [
        {
          "id": "custom-tool-uuid",
          "name": "get_weather",
          "is_available": true,
          ...
        },
        {
          "id": "vision-tool-uuid",
          "name": "analyze_image",
          "is_available": false,
          "missing_capabilities": ["vision"],
          "unavailable_reason": "Model doesn't support: vision"
        }
      ]
    }
    ```
    """
    service = AssistantToolsService(db)
    result = await service.get_available_tools_for_model(
        model_id=model_id,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )

    return result


@router.get(
    "/assistant/{assistant_id}",
    response_model=AvailableToolsResponse,
    summary="Get tools for existing assistant",
)
async def get_assistant_tools(
    assistant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get tools configured for an existing assistant.

    Returns available tools with `is_enabled` indicating which
    tools are currently configured for the assistant.
    """
    service = AssistantToolsService(db)
    result = await service.get_tools_for_assistant(assistant_id)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )

    return result


@router.post(
    "/validate",
    response_model=ValidateToolsResponse,
    summary="Validate tool selection",
)
async def validate_tools(
    request: ValidateToolsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Validate that selected tools are compatible with the model.

    Call this before saving an assistant to ensure the tool
    configuration is valid.

    Returns:
    - **valid**: True if all tools are compatible
    - **errors**: List of validation errors if any
    - **validated_builtin_tools**: Tools that passed validation
    - **validated_custom_tools**: Custom tools that passed validation

    Example request:
    ```json
    {
      "model_id": "model-uuid",
      "builtin_tool_names": ["file_search", "code_interpreter"],
      "custom_tool_ids": ["tool-uuid-1", "tool-uuid-2"]
    }
    ```
    """
    service = AssistantToolsService(db)
    result = await service.validate_tools_for_model(
        model_id=UUID(request.model_id),
        builtin_tool_names=request.builtin_tool_names,
        custom_tool_ids=request.custom_tool_ids,
    )

    return result


@router.get(
    "/builtin/{vendor}",
    summary="Get all built-in tools for a vendor",
)
async def get_vendor_builtin_tools(
    vendor: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all built-in tools available for a vendor.

    This returns the complete list of built-in tools for a vendor,
    regardless of model. Use this for documentation or to show
    what tools exist.
    """
    from src.services.builtin_tool_service import BuiltinToolService

    service = BuiltinToolService(db)
    tools = await service.get_tools_by_provider_name(vendor.lower())

    if not tools:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tools found for vendor: {vendor}",
        )

    return {
        "vendor": vendor.lower(),
        "tools": [tool.to_dict() for tool in tools],
        "total": len(tools),
    }


@router.get(
    "/capabilities/required/{tool_id}",
    summary="Get required capabilities for a tool",
)
async def get_tool_required_capabilities(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the capabilities required by a custom tool.

    Useful to understand why a tool might not be available
    for a specific model.
    """
    from sqlalchemy import select
    from src.models.capability import ToolCapabilityRequirement

    result = await db.execute(
        select(ToolCapabilityRequirement).where(
            ToolCapabilityRequirement.tool_id == str(tool_id)
        )
    )
    requirements = list(result.scalars().all())

    return {
        "tool_id": str(tool_id),
        "required_capabilities": [
            {
                "capability_type": req.capability_type.value,
                "is_required": req.is_required,
                "reason": req.reason,
            }
            for req in requirements
        ],
    }
