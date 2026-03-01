"""Capability Management API Routes.

This module provides endpoints for managing capabilities across the platform:
- Manage capability definitions, vendor mappings, model capabilities
- View available capabilities

All endpoints require an authenticated user (no role checks).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.capability import CapabilityType
from src.services.capability_service import CapabilityService


router = APIRouter(prefix="/capabilities", tags=["Capabilities"])


# ==================== Schemas ====================

class CapabilityDefinitionResponse(BaseModel):
    """Capability definition for API response."""
    capability_type: str
    display_name: str
    description: str | None
    icon: str | None
    category: str
    config_schema: dict
    default_config: dict
    is_premium: bool
    is_beta: bool
    is_deprecated: bool
    sort_order: int

    class Config:
        from_attributes = True


class ModelCapabilityResponse(BaseModel):
    """Model capability mapping for API response."""
    id: str
    model_id: str
    capability_type: str
    is_enabled: bool
    config: dict
    vendor_implementation: dict
    limitations: str | None

    class Config:
        from_attributes = True


class SetModelCapabilityRequest(BaseModel):
    """Request to set a capability for a model."""
    capability_type: str
    is_enabled: bool = True
    config: dict = Field(default_factory=dict)
    vendor_implementation: dict = Field(default_factory=dict)


class BulkSetCapabilitiesRequest(BaseModel):
    """Request to set multiple capabilities for a model."""
    capabilities: list[SetModelCapabilityRequest]


class CapabilitySummaryResponse(BaseModel):
    """Summary of capabilities for a model."""
    model_id: str
    enabled_capabilities: list[dict]
    disabled_capabilities: list[dict]
    total_enabled: int
    total_disabled: int


class ToolCompatibilityRequest(BaseModel):
    """Request to check tool compatibility."""
    tool_ids: list[str]
    model_id: str


class ToolCompatibilityResponse(BaseModel):
    """Tool compatibility check result."""
    compatible_tools: list[str]
    incompatible_tools: list[dict]


class VendorMappingResponse(BaseModel):
    """Vendor capability mapping for API response."""
    id: str
    provider_id: str
    capability_type: str
    vendor_name: str
    invocation_method: str
    api_config: dict
    default_params: dict
    supported_model_patterns: list[str]
    excluded_model_patterns: list[str]
    is_available: bool
    notes: str | None

    class Config:
        from_attributes = True


class UpdateVendorMappingRequest(BaseModel):
    """Request to update vendor capability mapping."""
    vendor_name: str | None = None
    invocation_method: str | None = None
    api_config: dict | None = None
    default_params: dict | None = None
    supported_model_patterns: list[str] | None = None
    excluded_model_patterns: list[str] | None = None
    is_available: bool | None = None
    notes: str | None = None


# ==================== Capability Definitions ====================

@router.get(
    "/definitions",
    response_model=list[CapabilityDefinitionResponse],
    summary="List capability definitions",
)
async def list_capability_definitions(
    category: str | None = None,
    include_beta: bool = True,
    include_deprecated: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all capability definitions.

    Available to all authenticated users for reference.
    """
    service = CapabilityService(db)
    definitions = await service.list_capability_definitions(
        category=category,
        include_beta=include_beta,
        include_deprecated=include_deprecated,
    )
    return definitions


@router.put(
    "/definitions/{capability_type}",
    response_model=CapabilityDefinitionResponse,
    summary="Update capability definition",
    dependencies=[Depends(get_current_user)],
)
async def update_capability_definition(
    capability_type: str,
    updates: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """Update a capability definition.

    Allows updating display information, configuration schema,
    and vendor mappings for a capability.
    """
    try:
        cap_type = CapabilityType(capability_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid capability type: {capability_type}",
        )

    service = CapabilityService(db)
    definition = await service.update_capability_definition(cap_type, updates)
    return definition


@router.post(
    "/seed",
    summary="Seed default capabilities",
    dependencies=[Depends(get_current_user)],
)
async def seed_capabilities(
    db: AsyncSession = Depends(get_db),
):
    """Seed default capability definitions.

    Creates default capability definitions if they don't exist.
    Safe to call multiple times - only creates missing entries.
    """
    service = CapabilityService(db)
    await service.seed_default_capabilities()
    return {"message": "Capability definitions seeded successfully"}


# ==================== Model Capabilities ====================

@router.get(
    "/models/{model_id}",
    response_model=list[ModelCapabilityResponse],
    summary="Get model capabilities",
)
async def get_model_capabilities(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all capabilities for a specific model.

    Available to all authenticated users.
    """
    service = CapabilityService(db)
    capabilities = await service.get_model_capabilities(model_id)
    return capabilities


@router.get(
    "/models/{model_id}/summary",
    response_model=CapabilitySummaryResponse,
    summary="Get model capability summary",
)
async def get_model_capability_summary(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a user-friendly summary of model capabilities.

    Returns enabled and disabled capabilities with display names.
    """
    service = CapabilityService(db)
    summary = await service.get_capability_summary(model_id)
    return summary


@router.post(
    "/models/{model_id}",
    response_model=ModelCapabilityResponse,
    summary="Set model capability",
    dependencies=[Depends(get_current_user)],
)
async def set_model_capability(
    model_id: UUID,
    request: SetModelCapabilityRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set a capability for a model.

    Enables or disables a specific capability for a model,
    with optional configuration.
    """
    try:
        cap_type = CapabilityType(request.capability_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid capability type: {request.capability_type}",
        )

    service = CapabilityService(db)
    capability = await service.set_model_capability(
        model_id=model_id,
        capability_type=cap_type,
        is_enabled=request.is_enabled,
        config=request.config,
        vendor_implementation=request.vendor_implementation,
    )
    return capability


@router.post(
    "/models/{model_id}/bulk",
    response_model=list[ModelCapabilityResponse],
    summary="Bulk set model capabilities",
    dependencies=[Depends(get_current_user)],
)
async def bulk_set_model_capabilities(
    model_id: UUID,
    request: BulkSetCapabilitiesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set multiple capabilities for a model at once."""
    service = CapabilityService(db)

    capabilities_data = []
    for cap in request.capabilities:
        try:
            cap_type = CapabilityType(cap.capability_type)
            capabilities_data.append({
                "capability_type": cap_type,
                "is_enabled": cap.is_enabled,
                "config": cap.config,
                "vendor_implementation": cap.vendor_implementation,
            })
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid capability type: {cap.capability_type}",
            )

    results = await service.bulk_set_model_capabilities(model_id, capabilities_data)
    return results


@router.post(
    "/models/{model_id}/auto-detect",
    response_model=list[ModelCapabilityResponse],
    summary="Auto-detect model capabilities",
    dependencies=[Depends(get_current_user)],
)
async def auto_detect_model_capabilities(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Auto-detect capabilities for a model.

    Uses vendor mappings and model patterns to automatically
    detect and set capabilities for a model.
    """
    service = CapabilityService(db)
    capabilities = await service.auto_detect_model_capabilities(model_id)
    return capabilities


@router.get(
    "/models/{model_id}/supports/{capability_type}",
    summary="Check if model supports capability",
)
async def check_model_supports_capability(
    model_id: UUID,
    capability_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Check if a model supports a specific capability."""
    try:
        cap_type = CapabilityType(capability_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid capability type: {capability_type}",
        )

    service = CapabilityService(db)
    supports = await service.model_supports_capability(model_id, cap_type)

    return {
        "model_id": str(model_id),
        "capability_type": capability_type,
        "supports": supports,
    }


# ==================== Tool Compatibility ====================

@router.post(
    "/tools/check-compatibility",
    response_model=ToolCompatibilityResponse,
    summary="Check tool compatibility with model",
)
async def check_tool_compatibility(
    request: ToolCompatibilityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Check which tools are compatible with a model.

    Returns lists of compatible and incompatible tools,
    with reasons for incompatibility.
    """
    service = CapabilityService(db)

    compatible = []
    incompatible = []

    for tool_id_str in request.tool_ids:
        tool_id = UUID(tool_id_str)
        model_id = UUID(request.model_id)

        is_valid, missing = await service.validate_tool_for_model(tool_id, model_id)

        if is_valid:
            compatible.append(tool_id_str)
        else:
            incompatible.append({
                "tool_id": tool_id_str,
                "missing_capabilities": missing,
                "reason": f"Model doesn't support: {', '.join(missing)}",
            })

    return {
        "compatible_tools": compatible,
        "incompatible_tools": incompatible,
    }


@router.get(
    "/tools/{tool_id}/validate/{model_id}",
    summary="Validate tool for model",
)
async def validate_tool_for_model(
    tool_id: UUID,
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Validate if a specific tool can be used with a model."""
    service = CapabilityService(db)
    is_valid, missing = await service.validate_tool_for_model(tool_id, model_id)

    return {
        "tool_id": str(tool_id),
        "model_id": str(model_id),
        "is_valid": is_valid,
        "missing_capabilities": missing,
        "message": "Tool is compatible" if is_valid else f"Missing capabilities: {', '.join(missing)}",
    }


# ==================== Vendor Mappings ====================

@router.get(
    "/vendors/{provider_id}",
    response_model=list[VendorMappingResponse],
    summary="Get vendor capability mappings",
    dependencies=[Depends(get_current_user)],
)
async def get_vendor_capability_mappings(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all capability mappings for a vendor/provider."""
    from sqlalchemy import select
    from src.models.capability import VendorCapabilityMapping

    result = await db.execute(
        select(VendorCapabilityMapping).where(
            VendorCapabilityMapping.provider_id == str(provider_id)
        )
    )
    mappings = list(result.scalars().all())
    return mappings


@router.put(
    "/vendors/{provider_id}/{capability_type}",
    response_model=VendorMappingResponse,
    summary="Update vendor capability mapping",
    dependencies=[Depends(get_current_user)],
)
async def update_vendor_capability_mapping(
    provider_id: UUID,
    capability_type: str,
    request: UpdateVendorMappingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update vendor-specific capability mapping.

    Configures how a capability is invoked for a specific vendor.
    """
    try:
        cap_type = CapabilityType(capability_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid capability type: {capability_type}",
        )

    service = CapabilityService(db)

    # Build updates dict from non-None values
    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    mapping = await service.update_vendor_capability_mapping(
        provider_id, cap_type, updates
    )
    return mapping


@router.post(
    "/vendors/{provider_id}/seed",
    summary="Seed vendor capability mappings",
    dependencies=[Depends(get_current_user)],
)
async def seed_vendor_mappings(
    provider_id: UUID,
    provider_name: str = Query(..., description="Provider name (e.g., 'openai', 'anthropic')"),
    db: AsyncSession = Depends(get_db),
):
    """Seed default capability mappings for a vendor."""
    service = CapabilityService(db)
    await service.seed_vendor_mappings(provider_id, provider_name)
    return {"message": f"Vendor mappings seeded for {provider_name}"}


# ==================== Capability Types Reference ====================

@router.get(
    "/types",
    summary="List all capability types",
)
async def list_capability_types():
    """List all available capability types.

    This is a reference endpoint showing all possible capability types
    in the system.
    """
    return {
        "capability_types": [
            {
                "value": cap.value,
                "name": cap.name,
                "description": _get_capability_description(cap),
            }
            for cap in CapabilityType
        ]
    }


def _get_capability_description(cap: CapabilityType) -> str:
    """Get description for a capability type."""
    descriptions = {
        CapabilityType.FILE_SEARCH: "Search through uploaded files",
        CapabilityType.CODE_INTERPRETER: "Execute Python code in sandbox",
        CapabilityType.WEB_SEARCH: "Search the internet",
        CapabilityType.IMAGE_GENERATION: "Generate images from text",
        CapabilityType.VISION: "Analyze images",
        CapabilityType.AUDIO_INPUT: "Process audio input",
        CapabilityType.AUDIO_OUTPUT: "Generate speech",
        CapabilityType.VIDEO_INPUT: "Process video",
        CapabilityType.VIDEO_OUTPUT: "Generate video",
        CapabilityType.FUNCTION_CALLING: "Call custom functions",
        CapabilityType.PARALLEL_FUNCTIONS: "Call multiple functions at once",
        CapabilityType.STRUCTURED_OUTPUT: "Generate structured JSON",
        CapabilityType.EXTENDED_THINKING: "Advanced reasoning mode",
        CapabilityType.CHAIN_OF_THOUGHT: "Show reasoning steps",
        CapabilityType.LONG_CONTEXT: "100k+ context window",
        CapabilityType.STREAMING: "Stream responses",
        CapabilityType.ARTIFACTS: "Create rich artifacts",
        CapabilityType.COMPUTER_USE: "Control computer",
        CapabilityType.MCP: "Model Context Protocol",
    }
    return descriptions.get(cap, cap.value)
