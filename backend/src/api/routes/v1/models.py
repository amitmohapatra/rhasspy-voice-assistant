"""AI Model Registry API - Manage AI providers and models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.deps import DbSession, CurrentUser
from src.core.exceptions import NotFoundError, ValidationError
from src.models.ai_model import (
    ProviderStatus,
    ModelStatus,
    ModelCategory,
    ModelTier,
)
from src.services.model_registry import ModelRegistryService

router = APIRouter()


# ==================== Pydantic Schemas ====================

class ProviderBase(BaseModel):
    """Base provider schema."""
    name: str = Field(..., max_length=100)
    display_name: str = Field(..., max_length=200)
    description: str | None = None
    website: str | None = None
    docs_url: str | None = None
    provider_type: str = "llm"
    base_url: str | None = None
    api_version: str | None = None
    required_secrets: list[str] | None = None
    supports_streaming: bool = True
    supports_function_calling: bool = True
    supports_vision: bool = False
    supports_audio: bool = False
    default_rpm: int | None = None
    default_tpm: int | None = None
    logo_url: str | None = None
    color: str | None = None
    sort_order: int = 100


class ProviderCreate(ProviderBase):
    """Schema for creating a provider."""
    pass


class ProviderUpdate(BaseModel):
    """Schema for updating a provider."""
    display_name: str | None = None
    description: str | None = None
    website: str | None = None
    docs_url: str | None = None
    base_url: str | None = None
    api_version: str | None = None
    required_secrets: list[str] | None = None
    supports_streaming: bool | None = None
    supports_function_calling: bool | None = None
    supports_vision: bool | None = None
    supports_audio: bool | None = None
    default_rpm: int | None = None
    default_tpm: int | None = None
    logo_url: str | None = None
    color: str | None = None
    sort_order: int | None = None


class ProviderStatusUpdate(BaseModel):
    """Schema for updating provider status."""
    status: ProviderStatus
    status_message: str | None = None


class ProviderResponse(ProviderBase):
    """Provider response schema."""
    id: UUID
    status: ProviderStatus
    status_message: str | None
    created_at: datetime
    updated_at: datetime
    model_count: int | None = None

    class Config:
        from_attributes = True


class ModelBase(BaseModel):
    """Base model schema."""
    model_id: str = Field(..., max_length=200, description="Official model ID for API calls")
    name: str = Field(..., max_length=200)
    display_name: str = Field(..., max_length=300)
    aliases: list[str] | None = None
    version: str | None = None
    release_date: datetime | None = None
    category: ModelCategory = ModelCategory.CHAT
    tier: ModelTier = ModelTier.STANDARD
    short_description: str | None = Field(None, max_length=500)
    description: str | None = None
    best_for: list[str] | None = None
    limitations: list[str] | None = None
    context_window: int = 4096
    max_output_tokens: int | None = None
    supports_tools: bool = True
    supports_vision: bool = False
    supports_audio: bool = False
    supports_video: bool = False
    supports_streaming: bool = True
    supports_json_mode: bool = False
    supports_system_prompt: bool = True
    is_reasoning_model: bool = False
    is_moe: bool = False
    is_fine_tunable: bool = False
    is_distilled: bool = False
    parameter_count: str | None = None
    architecture: str | None = None
    training_cutoff: str | None = None
    input_price_per_1m: Decimal | None = None
    output_price_per_1m: Decimal | None = None
    cached_input_price_per_1m: Decimal | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    rpd_limit: int | None = None
    default_temperature: float | None = None
    default_top_p: float | None = None
    default_max_tokens: int | None = None
    recommended_temperature: float | None = None
    supported_languages: list[str] | None = None
    config: dict | None = None
    icon: str | None = None
    color: str | None = None
    badge: str | None = None
    sort_order: int = 100
    is_featured: bool = False
    is_default: bool = False


class ModelCreate(ModelBase):
    """Schema for creating a model."""
    provider_id: UUID | None = None
    provider_name: str | None = None  # Alternative to provider_id


class ModelUpdate(BaseModel):
    """Schema for updating a model."""
    display_name: str | None = None
    aliases: list[str] | None = None
    version: str | None = None
    category: ModelCategory | None = None
    tier: ModelTier | None = None
    short_description: str | None = None
    description: str | None = None
    best_for: list[str] | None = None
    limitations: list[str] | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_tools: bool | None = None
    supports_vision: bool | None = None
    supports_audio: bool | None = None
    supports_video: bool | None = None
    supports_streaming: bool | None = None
    supports_json_mode: bool | None = None
    is_reasoning_model: bool | None = None
    is_moe: bool | None = None
    parameter_count: str | None = None
    architecture: str | None = None
    training_cutoff: str | None = None
    input_price_per_1m: Decimal | None = None
    output_price_per_1m: Decimal | None = None
    cached_input_price_per_1m: Decimal | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    default_temperature: float | None = None
    recommended_temperature: float | None = None
    config: dict | None = None
    badge: str | None = None
    sort_order: int | None = None
    is_featured: bool | None = None
    is_default: bool | None = None


class ModelStatusUpdate(BaseModel):
    """Schema for updating model status."""
    status: ModelStatus
    deprecation_date: datetime | None = None
    retirement_date: datetime | None = None


class ModelResponse(ModelBase):
    """Model response schema."""
    id: UUID
    provider_id: UUID
    status: ModelStatus
    deprecation_date: datetime | None
    retirement_date: datetime | None
    created_at: datetime
    updated_at: datetime
    provider_name: str | None = None
    provider_display_name: str | None = None

    class Config:
        from_attributes = True


class ModelListResponse(BaseModel):
    """Paginated model list response."""
    models: list[ModelResponse]
    total: int
    limit: int
    offset: int


class ModelComparisonResponse(BaseModel):
    """Model comparison response."""
    models: list[dict[str, Any]]


class ProviderStatsResponse(BaseModel):
    """Provider statistics response."""
    provider_id: str
    provider_name: str
    total_models: int
    active_models: int
    models_by_status: dict[str, int]
    models_by_category: dict[str, int]


class InitializeResponse(BaseModel):
    """Response for initialization endpoint."""
    providers_created: int
    models_created: int
    message: str


# ==================== Provider Endpoints ====================

@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(
    db: DbSession,
    status: ProviderStatus | None = None,
    provider_type: str | None = None,
    include_model_count: bool = True,
):
    """List all AI providers.

    - **status**: Filter by status (active, disabled, etc.)
    - **provider_type**: Filter by type (llm, image, audio, video)
    - **include_model_count**: Include count of models per provider
    """
    service = ModelRegistryService(db)
    providers = await service.list_providers(
        status=status,
        provider_type=provider_type,
        include_models=include_model_count,
    )

    result = []
    for p in providers:
        response = ProviderResponse.model_validate(p)
        if include_model_count and hasattr(p, 'models'):
            response.model_count = len(p.models)
        result.append(response)

    return result


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: UUID,
    db: DbSession,
):
    """Get a specific provider by ID."""
    service = ModelRegistryService(db)
    try:
        provider = await service.get_provider(
            provider_id=provider_id,
            include_models=True,
        )
        response = ProviderResponse.model_validate(provider)
        response.model_count = len(provider.models)
        return response
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")


@router.get("/providers/name/{name}", response_model=ProviderResponse)
async def get_provider_by_name(
    name: str,
    db: DbSession,
):
    """Get a provider by name (e.g., 'openai', 'anthropic')."""
    service = ModelRegistryService(db)
    try:
        provider = await service.get_provider(name=name, include_models=True)
        response = ProviderResponse.model_validate(provider)
        response.model_count = len(provider.models)
        return response
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")


@router.post("/providers", response_model=ProviderResponse, status_code=201)
async def create_provider(
    data: ProviderCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new AI provider."""
    service = ModelRegistryService(db)
    provider = await service.create_provider(data.model_dump())
    return ProviderResponse.model_validate(provider)


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    data: ProviderUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update a provider."""
    service = ModelRegistryService(db)
    try:
        provider = await service.update_provider(
            provider_id,
            data.model_dump(exclude_unset=True),
        )
        return ProviderResponse.model_validate(provider)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")


@router.patch("/providers/{provider_id}/status", response_model=ProviderResponse)
async def update_provider_status(
    provider_id: UUID,
    data: ProviderStatusUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Enable, disable, or set maintenance mode for a provider."""
    service = ModelRegistryService(db)
    try:
        provider = await service.update_provider_status(
            provider_id,
            data.status,
            data.status_message,
        )
        return ProviderResponse.model_validate(provider)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Delete a provider and all its models."""
    service = ModelRegistryService(db)
    try:
        await service.delete_provider(provider_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")


@router.get("/providers/{provider_id}/stats", response_model=ProviderStatsResponse)
async def get_provider_stats(
    provider_id: UUID,
    db: DbSession,
):
    """Get statistics for a provider."""
    service = ModelRegistryService(db)
    try:
        stats = await service.get_provider_stats(provider_id)
        return ProviderStatsResponse(**stats)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Provider not found")


# ==================== Model Endpoints ====================

@router.get("/models", response_model=ModelListResponse)
async def list_models(
    db: DbSession,
    provider_id: UUID | None = None,
    provider_name: str | None = Query(None, description="Filter by provider name"),
    status: ModelStatus | None = None,
    category: ModelCategory | None = None,
    tier: ModelTier | None = None,
    supports_tools: bool | None = None,
    supports_vision: bool | None = None,
    is_reasoning_model: bool | None = None,
    is_featured: bool | None = None,
    search: str | None = Query(None, description="Search in name, description"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List AI models with filtering and pagination.

    Supports filtering by:
    - **provider_id/provider_name**: Specific provider
    - **status**: Model status (active, deprecated, disabled)
    - **category**: Model category (chat, reasoning, coding, vision, etc.)
    - **tier**: Pricing tier (free, standard, premium, enterprise)
    - **supports_tools/vision**: Capability filters
    - **is_reasoning_model**: Extended thinking models
    - **is_featured**: Featured/recommended models
    - **search**: Text search in name and description
    """
    service = ModelRegistryService(db)
    models, total = await service.list_models(
        provider_id=provider_id,
        provider_name=provider_name,
        status=status,
        category=category,
        tier=tier,
        supports_tools=supports_tools,
        supports_vision=supports_vision,
        is_reasoning_model=is_reasoning_model,
        is_featured=is_featured,
        search=search,
        limit=limit,
        offset=offset,
    )

    return ModelListResponse(
        models=[_model_to_response(m) for m in models],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/models/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: UUID,
    db: DbSession,
):
    """Get a specific model by ID."""
    service = ModelRegistryService(db)
    try:
        model = await service.get_model(model_id=model_id)
        return _model_to_response(model)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/models/lookup/{model_identifier}", response_model=ModelResponse)
async def lookup_model(
    model_identifier: str,
    db: DbSession,
    provider_name: str | None = Query(None, description="Provider to search in"),
):
    """Look up a model by model_id, name, or alias.

    Examples:
    - `/models/lookup/gpt-5.2`
    - `/models/lookup/claude-opus?provider_name=anthropic`
    - `/models/lookup/llama-4-maverick`
    """
    service = ModelRegistryService(db)
    try:
        model = await service.get_model(
            model_identifier=model_identifier,
            provider_name=provider_name,
        )
        return _model_to_response(model)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.post("/models", response_model=ModelResponse, status_code=201)
async def create_model(
    data: ModelCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new AI model."""
    service = ModelRegistryService(db)
    try:
        model = await service.create_model(data.model_dump())
        return _model_to_response(model)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/models/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: UUID,
    data: ModelUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update a model."""
    service = ModelRegistryService(db)
    try:
        model = await service.update_model(
            model_id,
            data.model_dump(exclude_unset=True),
        )
        return _model_to_response(model)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.patch("/models/{model_id}/status", response_model=ModelResponse)
async def update_model_status(
    model_id: UUID,
    data: ModelStatusUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update model status (enable, disable, deprecate)."""
    service = ModelRegistryService(db)
    try:
        model = await service.update_model_status(
            model_id,
            data.status,
            data.deprecation_date,
            data.retirement_date,
        )
        return _model_to_response(model)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Delete a model."""
    service = ModelRegistryService(db)
    try:
        await service.delete_model(model_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Model not found")


# ==================== Discovery Endpoints ====================

@router.get("/models/recommend/{task_type}", response_model=list[ModelResponse])
async def get_recommended_models(
    task_type: str,
    db: DbSession,
    require_tools: bool = False,
    require_vision: bool = False,
    max_context_needed: int | None = None,
    budget_tier: ModelTier | None = None,
):
    """Get recommended models for a specific task type.

    Task types:
    - **chat**: General conversation
    - **coding**: Code generation and editing
    - **reasoning**: Complex problem-solving
    - **analysis**: Data analysis and research
    - **vision**: Image understanding
    - **embedding**: Text embeddings
    - **translation**: Language translation
    """
    service = ModelRegistryService(db)
    models = await service.get_models_for_task(
        task_type=task_type,
        require_tools=require_tools,
        require_vision=require_vision,
        max_context_needed=max_context_needed,
        budget_tier=budget_tier,
    )
    return [_model_to_response(m) for m in models]


@router.get("/models/default", response_model=ModelResponse | None)
async def get_default_model(
    db: DbSession,
    provider_name: str | None = None,
    category: ModelCategory = ModelCategory.CHAT,
):
    """Get the default model for a provider or category."""
    service = ModelRegistryService(db)
    model = await service.get_default_model(
        provider_name=provider_name,
        category=category,
    )
    if model:
        return _model_to_response(model)
    return None


@router.post("/models/compare", response_model=ModelComparisonResponse)
async def compare_models(
    model_ids: list[UUID],
    db: DbSession,
):
    """Compare multiple models side-by-side.

    Returns key attributes for comparison including:
    - Context window
    - Capabilities (tools, vision, reasoning)
    - Pricing
    - Best use cases and limitations
    """
    if len(model_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 models required for comparison"
        )
    if len(model_ids) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 models can be compared at once"
        )

    service = ModelRegistryService(db)
    comparison = await service.get_model_comparison(model_ids)
    return ModelComparisonResponse(models=comparison)


@router.get("/models/resolve/{alias}")
async def resolve_model_alias(
    alias: str,
    db: DbSession,
    provider_name: str | None = None,
):
    """Resolve a model alias to the official model_id.

    Useful for mapping friendly names like 'gpt-4' to full IDs.
    """
    service = ModelRegistryService(db)
    model_id = await service.resolve_model_alias(alias, provider_name)
    if model_id:
        return {"alias": alias, "model_id": model_id}
    raise HTTPException(status_code=404, detail="Alias not found")


# ==================== Admin Endpoints ====================

@router.post("/initialize", response_model=InitializeResponse)
async def initialize_registry(
    db: DbSession,
    user: CurrentUser,
):
    """Initialize the model registry with default providers and sample models.

    This endpoint populates the database with:
    - Default AI providers (OpenAI, Anthropic, Google, etc.)
    - Sample models with full metadata

    Safe to call multiple times - only creates missing entries.
    """
    service = ModelRegistryService(db)
    result = await service.initialize_defaults()
    return InitializeResponse(
        providers_created=result["providers_created"],
        models_created=result["models_created"],
        message=f"Initialized {result['providers_created']} providers and {result['models_created']} models",
    )


@router.post("/providers/{provider_id}/disable-all-models")
async def disable_all_provider_models(
    provider_id: UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Disable all models for a provider.

    Useful when a provider is experiencing issues or being deprecated.
    """
    service = ModelRegistryService(db)
    count = await service.bulk_update_model_status(
        provider_id=provider_id,
        new_status=ModelStatus.DISABLED,
    )
    return {"disabled_count": count}


# ==================== Helper Functions ====================

def _model_to_response(model) -> ModelResponse:
    """Convert model ORM object to response schema."""
    response = ModelResponse.model_validate(model)
    if model.provider:
        response.provider_name = model.provider.name
        response.provider_display_name = model.provider.display_name
    return response
