"""Chat routes — conversation management (list, responses, delete).

The POST endpoint for creating responses has moved to /api/v1/responses.
This module retains conversation management endpoints.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.deps import DbSession, CurrentUser
from src.schemas.response import ResponseSchema
from src.services.response_service import ResponseService

router = APIRouter()


@router.get("/conversations/{conversation_id}/responses")
async def get_conversation_responses(
    conversation_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 50,
) -> list[ResponseSchema]:
    """Get all responses for a conversation with their output items."""
    service = ResponseService(db)
    responses = await service.list_conversation_responses(
        conversation_id=conversation_id,
        limit=limit,
    )
    return [ResponseSchema.from_model(r) for r in responses]


@router.get("/conversations")
async def list_conversations(
    db: DbSession,
    current_user: CurrentUser,
    assistant_id: UUID | None = None,
    limit: int = 50,
) -> list[dict]:
    """List conversations for the current user."""
    from sqlalchemy import select
    from src.models.conversation import Conversation

    query = select(Conversation).where(
        Conversation.user_id == current_user.id,
        Conversation.status == "active",
    )

    if assistant_id:
        query = query.where(Conversation.assistant_id == assistant_id)

    query = query.order_by(Conversation.updated_at.desc()).limit(limit)

    result = await db.execute(query)
    conversations = result.scalars().all()

    return [
        {
            "id": str(conv.id),
            "assistant_id": str(conv.assistant_id),
            "title": conv.title,
            "response_count": conv.response_count or 0,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        }
        for conv in conversations
    ]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a conversation (soft delete)."""
    from sqlalchemy import select
    from src.models.conversation import Conversation

    query = select(Conversation).where(
        Conversation.id == conversation_id,
    )
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Soft delete
    conversation.status = "deleted"
    await db.flush()
