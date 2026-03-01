"""Assistant routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import DbSession, CurrentUser
from src.core.exceptions import NotFoundError, ValidationError
from src.schemas.assistant import AssistantCreate, AssistantUpdate, AssistantResponse, AssistantListResponse
from src.services.assistant_service import AssistantService

router = APIRouter()


@router.post("", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
async def create_assistant(
    data: AssistantCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AssistantResponse:
    """Create a new assistant."""
    try:
        service = AssistantService(db)
        assistant = await service.create(data, user_id=current_user.id)
        return AssistantResponse.model_validate(assistant)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get("", response_model=AssistantListResponse)
async def list_assistants(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    active_only: bool = Query(True),
    search: str | None = Query(None, description="Search by name or description"),
) -> AssistantListResponse:
    """List assistants."""
    service = AssistantService(db)
    assistants, total = await service.list(
        skip=skip,
        limit=limit,
        active_only=active_only,
        search=search,
        user_id=current_user.id,
    )

    page = (skip // limit) + 1 if limit > 0 else 1
    return AssistantListResponse(
        items=[AssistantResponse.model_validate(a) for a in assistants],
        total=total,
        page=page,
        page_size=limit,
        has_more=(skip + limit) < total,
    )


@router.get("/{assistant_id}", response_model=AssistantResponse)
async def get_assistant(
    assistant_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> AssistantResponse:
    """Get an assistant by ID."""
    try:
        service = AssistantService(db)
        assistant = await service.get(assistant_id)
        return AssistantResponse.model_validate(assistant)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put("/{assistant_id}", response_model=AssistantResponse)
async def update_assistant(
    assistant_id: UUID,
    data: AssistantUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AssistantResponse:
    """Update an assistant."""
    try:
        service = AssistantService(db)
        assistant = await service.update(
            assistant_id, data
        )
        return AssistantResponse.model_validate(assistant)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(
    assistant_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete an assistant."""
    try:
        service = AssistantService(db)
        await service.delete(assistant_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
