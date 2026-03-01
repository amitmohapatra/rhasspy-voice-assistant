"""Document-scoped chat endpoint — SSE streaming with document-filtered RAG.

POST /api/v1/documents/{document_id}/chat
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.deps import DbSession, CurrentUser
from src.services.knowledge_base_service import KnowledgeBaseService
from src.services.document_chat_service import DocumentChatService
from src.services import llm_key_service

router = APIRouter()


class DocumentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    provider: str = Field(default="openai")
    model: str = Field(default="gpt-4o")
    conversation_history: list[dict] | None = None


@router.post("/{document_id}/chat")
async def document_chat(
    document_id: UUID,
    request: DocumentChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Chat with a specific document using document-scoped RAG."""
    # Verify document exists and user owns it
    service = KnowledgeBaseService(db)
    document = await service.get_document(document_id)

    if document.uploaded_by and document.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only chat with your own documents",
        )

    if document.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document must be processed before chatting (status: {document.status})",
        )

    # Resolve user's LLM vendor key (fallback to platform key)
    user_api_key = await llm_key_service.get_user_llm_key(
        db, current_user.id, request.provider
    )

    chat_service = DocumentChatService(db)

    async def generate():
        try:
            async for event in chat_service.stream_response(
                document=document,
                message=request.message,
                provider=request.provider,
                model=request.model,
                user_api_key=user_api_key,
                conversation_history=request.conversation_history,
            ):
                yield event
        except Exception as e:
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
