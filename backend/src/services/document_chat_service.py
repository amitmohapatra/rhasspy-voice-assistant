"""Document Chat Service — document-scoped RAG chat with SSE streaming.

Provides chat scoped to a single document using the user's LLM vendor key
(falling back to platform key). RAG retrieval filters by document_id directly,
bypassing KB resolution.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.llm import LLMGateway, get_llm_gateway, Message as LLMMessage
from src.models.knowledge_base import Document
from src.services.rag_query_service import RAGQueryService

logger = logging.getLogger(__name__)


class DocumentChatService:
    """Chat service scoped to a single document.

    Uses document-filtered RAG and the user's own LLM vendor key.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.gateway = get_llm_gateway()
        self.rag_query = RAGQueryService(db)

    async def stream_response(
        self,
        document: Document,
        message: str,
        provider: str,
        model: str,
        user_api_key: str | None = None,
        conversation_history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a document-scoped chat response as SSE events.

        Args:
            document: The document to chat about.
            message: The user's message.
            provider: LLM provider name (e.g., "openai", "anthropic").
            model: Model name (e.g., "gpt-4o").
            user_api_key: User's decrypted API key (or None for platform key).
            conversation_history: Previous messages in the conversation.
        """
        response_id = str(uuid.uuid4())
        start = time.time()

        yield self._sse({
            "type": "response.created",
            "response": {
                "id": response_id,
                "status": "in_progress",
                "document_id": str(document.id),
            },
        })

        # Get RAG context filtered by this document
        rag_context = await self._get_document_context(
            query=message,
            document_id=str(document.id),
        )

        if rag_context:
            yield self._sse({
                "type": "response.output_item.added",
                "item": {
                    "item_type": "rag_context",
                    "content": rag_context[:500],
                },
            })

        # Build system prompt
        system_prompt = self._build_system_prompt(document, rag_context)

        # Build messages
        messages = [LLMMessage(role="system", content=system_prompt)]
        if conversation_history:
            for msg in conversation_history:
                messages.append(LLMMessage(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                ))
        messages.append(LLMMessage(role="user", content=message))

        # Build provider config with user's API key
        provider_config = None
        if user_api_key:
            provider_config = {"api_key": user_api_key}

        # Stream from LLM
        full_content = ""
        input_tokens = 0
        output_tokens = 0

        try:
            async for delta in self.gateway.stream(
                messages=messages,
                model=model,
                provider=provider,
                temperature=0.7,
                max_tokens=4096,
                provider_config=provider_config,
            ):
                if delta.type == "text":
                    full_content += delta.content or ""
                    yield self._sse({
                        "type": "response.content.delta",
                        "delta": delta.content,
                    })
                elif delta.type == "finish":
                    if delta.input_tokens:
                        input_tokens = delta.input_tokens
                    if delta.output_tokens:
                        output_tokens = delta.output_tokens

            yield self._sse({
                "type": "response.content.done",
                "content": full_content,
            })

        except Exception as e:
            logger.error("Document chat streaming failed: %s", e)
            yield self._sse({
                "type": "response.failed",
                "error": {
                    "code": "streaming_error",
                    "message": str(e),
                },
            })
            return

        total_ms = (time.time() - start) * 1000

        yield self._sse({
            "type": "response.completed",
            "response": {
                "id": response_id,
                "status": "completed",
                "document_id": str(document.id),
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                "total_time_ms": round(total_ms, 1),
            },
        })

    async def _get_document_context(
        self,
        query: str,
        document_id: str,
        top_k: int = 5,
    ) -> str:
        """Get RAG context filtered by a single document ID."""
        pipeline = await self.rag_query._get_pipeline()

        filter_metadata = {"document_id": document_id}

        # Visual search (ColSmol — optional)
        visual_results = None
        from src.core.config import settings as app_settings
        if app_settings.colsmol_enabled:
            try:
                from src.clients.inference_client import get_inference_client
                inference_client = get_inference_client()
                visual_embedding = await inference_client.embed_visual_query(query)
                if visual_embedding:
                    visual_results = await pipeline.vector_store.search_page_images(
                        query_embedding=visual_embedding,
                        top_k=3,
                        filter_metadata=filter_metadata,
                    )
            except Exception:
                pass

        from src.rag.base import RAGConfig
        config = RAGConfig()
        query_result = await pipeline.query(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata,
            visual_results=visual_results,
        )

        return self.rag_query.format_context(query_result.results)

    def _build_system_prompt(self, document: Document, rag_context: str) -> str:
        """Build system prompt for document-scoped chat."""
        parts = [
            f"You are a helpful document analysis assistant. You are answering questions about the document: \"{document.filename}\".",
            "Use the provided context from the document to answer accurately. If the context doesn't contain enough information, say so.",
            "When referencing information, mention the page number and element type when available.",
        ]

        if rag_context:
            parts.append(f"\n## Document Context:\n{rag_context}")

        return "\n".join(parts)

    def _sse(self, data: dict) -> str:
        """Format as SSE event."""
        return f"data: {json.dumps(data)}\n\n"
