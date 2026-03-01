"""Model-Tool Support API — manage model/tool compatibility mappings."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import DbSession, CurrentUser
from src.services.model_tool_support_service import ModelToolSupportService

router = APIRouter(prefix="/model-tool-support", tags=["model-tool-support"])


# ==================== Schemas ====================


class ToolSupportEntry(BaseModel):
    id: str
    model_id: str
    builtin_tool_id: str
    is_supported: bool
    config_overrides: dict
    api_config_overrides: dict
    source: str

    class Config:
        from_attributes = True


class SetSupportRequest(BaseModel):
    is_supported: bool
    config_overrides: dict | None = None
    api_config_overrides: dict | None = None


class BulkSetSupportRequest(BaseModel):
    tool_flags: dict[str, bool] = Field(
        ...,
        description="Mapping of builtin_tool_id -> is_supported",
    )


# ==================== Endpoints ====================


@router.get(
    "/{model_id}",
    summary="List tool support for a model",
)
async def get_model_tool_support(
    model_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    """List all tool support entries for a given model."""
    service = ModelToolSupportService(db)
    tools = await service.get_supported_tools(model_id)
    return {"model_id": str(model_id), "tools": tools, "total": len(tools)}


@router.get(
    "/tool/{tool_id}",
    summary="List model support for a tool",
)
async def get_tool_model_support(
    tool_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """List all models that support a given tool."""
    service = ModelToolSupportService(db)
    models = await service.get_supported_models(tool_id)
    return {"tool_id": tool_id, "models": models, "total": len(models)}


@router.put(
    "/{model_id}/{tool_id}",
    summary="Toggle support for one model-tool pair",
)
async def set_model_tool_support(
    model_id: UUID,
    tool_id: str,
    request: SetSupportRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Set or toggle support for a specific model-tool pair."""
    service = ModelToolSupportService(db)
    row = await service.set_support(
        model_id=model_id,
        tool_id=tool_id,
        is_supported=request.is_supported,
        config_overrides=request.config_overrides,
        api_config_overrides=request.api_config_overrides,
    )
    return {
        "id": str(row.id),
        "model_id": str(row.model_id),
        "builtin_tool_id": row.builtin_tool_id,
        "is_supported": row.is_supported,
        "source": row.source,
    }


@router.post(
    "/{model_id}/bulk",
    summary="Bulk set support flags for a model",
)
async def bulk_set_model_tool_support(
    model_id: UUID,
    request: BulkSetSupportRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Bulk update support flags for multiple tools on a single model."""
    service = ModelToolSupportService(db)
    count = await service.bulk_set_support(model_id, request.tool_flags)
    return {"model_id": str(model_id), "updated": count}


@router.post(
    "/rebuild/{provider_id}",
    summary="Re-resolve patterns for a provider",
)
async def rebuild_provider_support(
    provider_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Re-resolve all model-tool support for a provider from pattern data.

    Deletes auto/seed rows and re-creates them. Manually set ('api') rows
    are preserved.
    """
    service = ModelToolSupportService(db)
    result = await service.rebuild_for_provider(provider_id)
    return {"provider_id": provider_id, **result}
