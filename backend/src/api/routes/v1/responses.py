"""Responses API routes — stateless response chaining with SSE streaming."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from src.api.deps import DbSession, CurrentUser
from src.schemas.response import CreateResponseRequest, ResponseSchema
from src.services.response_service import ResponseService

router = APIRouter()


@router.post("")
async def create_response(
    request: CreateResponseRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Create a response (streaming SSE).

    This is the main endpoint for chat interactions. Each call creates
    a single response. Use previous_response_id for multi-turn conversations.
    """
    service = ResponseService(db)

    async def generate():
        try:
            async for event in service.create_response_stream(
                user_id=current_user.id,
                request=request,
            ):
                yield event
        except Exception as e:
            import json
            yield f"data: {json.dumps({'type': 'response.failed', 'error': {'code': 'internal_error', 'message': str(e)}})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{response_id}")
async def get_response(
    response_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ResponseSchema:
    """Get a response by ID with all output items."""
    service = ResponseService(db)
    response = await service.get_response(response_id)
    return ResponseSchema.from_model(response)


@router.delete("/{response_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_response(
    response_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a response."""
    service = ResponseService(db)
    await service.delete_response(response_id)
