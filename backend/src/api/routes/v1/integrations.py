"""Integration catalog and user integration routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import DbSession, CurrentUser
from src.core.exceptions import NotFoundError, ValidationError
from src.schemas.integration import (
    IntegrationCatalogCreate,
    IntegrationCatalogResponse,
    IntegrationTestRequest,
    IntegrationTestResponse,
    UserIntegrationCreate,
    UserIntegrationResponse,
    UserIntegrationUpdate,
)
from src.services.integration_service import IntegrationService

router = APIRouter()


# ==================== Catalog ====================


@router.get("/catalog", response_model=list[IntegrationCatalogResponse])
async def list_catalog(
    db: DbSession,
    current_user: CurrentUser,
    category: str | None = Query(None, description="Filter by category"),
) -> list[IntegrationCatalogResponse]:
    """List all available integrations from the catalog."""
    service = IntegrationService(db)
    entries = await service.list_catalog(category=category)
    return [IntegrationCatalogResponse.model_validate(e) for e in entries]


@router.get("/catalog/{integration_id}", response_model=IntegrationCatalogResponse)
async def get_catalog_entry(
    integration_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> IntegrationCatalogResponse:
    """Get a single integration catalog entry."""
    try:
        service = IntegrationService(db)
        entry = await service.get_catalog_entry(integration_id)
        return IntegrationCatalogResponse.model_validate(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post(
    "/catalog",
    response_model=IntegrationCatalogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_entry(
    data: IntegrationCatalogCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> IntegrationCatalogResponse:
    """Create a new integration catalog entry."""
    try:
        service = IntegrationService(db)
        entry = await service.create_catalog_entry(data.model_dump())
        return IntegrationCatalogResponse.model_validate(entry)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=e.message
        )


# ==================== User Integrations ====================


@router.get("", response_model=list[UserIntegrationResponse])
async def list_user_integrations(
    db: DbSession,
    current_user: CurrentUser,
    enabled_only: bool = Query(False, description="Only return enabled integrations"),
) -> list[UserIntegrationResponse]:
    """List integrations enabled for current user."""
    service = IntegrationService(db)
    integrations = await service.list_user_integrations(
        user_id=current_user.id,
        enabled_only=enabled_only,
    )

    return [
        UserIntegrationResponse(
            id=str(ui.id),
            integration_id=str(ui.integration_id),
            is_verified=ui.is_verified,
            is_enabled=ui.is_enabled,
            config=ui.config,
            last_tested_at=ui.last_tested_at,
            test_error=ui.test_error,
            created_at=str(ui.created_at),
            updated_at=str(ui.updated_at),
            catalog=IntegrationCatalogResponse.model_validate(ui.catalog) if ui.catalog else None,
        )
        for ui in integrations
    ]


@router.post(
    "",
    response_model=UserIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enable_integration(
    data: UserIntegrationCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> UserIntegrationResponse:
    """Enable an integration."""
    try:
        service = IntegrationService(db)
        ui = await service.enable_integration(
            catalog_id=UUID(data.integration_id),
            credentials=data.credentials,
            config=data.config,
        )
        return UserIntegrationResponse(
            id=str(ui.id),
            integration_id=str(ui.integration_id),
            is_verified=ui.is_verified,
            is_enabled=ui.is_enabled,
            config=ui.config,
            last_tested_at=ui.last_tested_at,
            test_error=ui.test_error,
            created_at=str(ui.created_at),
            updated_at=str(ui.updated_at),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put("/{integration_id}", response_model=UserIntegrationResponse)
async def update_user_integration(
    integration_id: UUID,
    data: UserIntegrationUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> UserIntegrationResponse:
    """Update credentials, config, or enabled status for a user integration."""
    try:
        service = IntegrationService(db)
        ui = await service.update_user_integration(
            integration_id, data.model_dump(exclude_unset=True)
        )
        return UserIntegrationResponse(
            id=str(ui.id),
            integration_id=str(ui.integration_id),
            is_verified=ui.is_verified,
            is_enabled=ui.is_enabled,
            config=ui.config,
            last_tested_at=ui.last_tested_at,
            test_error=ui.test_error,
            created_at=str(ui.created_at),
            updated_at=str(ui.updated_at),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_integration(
    integration_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Remove an integration."""
    try:
        service = IntegrationService(db)
        await service.delete_user_integration(integration_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# ==================== Connection Testing ====================


@router.post("/test", response_model=IntegrationTestResponse)
async def test_integration(
    data: IntegrationTestRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> IntegrationTestResponse:
    """Test an integration connection with provided credentials."""
    try:
        service = IntegrationService(db)
        result = await service.test_connection(
            UUID(data.integration_id), data.credentials
        )
        return IntegrationTestResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/{integration_id}/verify", response_model=IntegrationTestResponse)
async def verify_user_integration(
    integration_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> IntegrationTestResponse:
    """Test and verify a saved user integration."""
    try:
        service = IntegrationService(db)
        result = await service.test_and_verify(integration_id)
        return IntegrationTestResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
