"""Document processing tasks.

Uses BGE-M3 triple embeddings and Qdrant with named vectors.
"""

import asyncio
from uuid import UUID

from src.worker import celery_app


def _create_session_factory():
    """Create a fresh async engine + session factory for Celery tasks.

    Each asyncio.run() call creates a new event loop, so we need a fresh
    engine that isn't bound to a previous loop.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from src.core.config import settings

    engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=5,
        echo=settings.debug,
        future=True,
    )
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@celery_app.task(bind=True, name="src.tasks.document.process_document")
def process_document(self, document_id: str) -> dict:
    """Process a document asynchronously.

    This task:
    1. Extracts text from the document (using Docling for supported formats)
    2. Chunks the text (element-aware for structured content)
    3. Generates BGE-M3 triple embeddings
    4. Stores chunks in PostgreSQL and vectors in Qdrant
    """
    # Reset singleton clients — asyncio.run() creates a new event loop,
    # and httpx.AsyncClient from a previous loop would be stale.
    from src.clients.inference_client import reset_inference_client
    reset_inference_client()

    return asyncio.run(_process_document_async(UUID(document_id)))


async def _process_document_async(document_id: UUID) -> dict:
    """Async implementation of document processing."""
    from src.services.knowledge_base_service import KnowledgeBaseService

    SessionLocal = _create_session_factory()

    async with SessionLocal() as db:
        try:
            service = KnowledgeBaseService(db)
            document = await service.process_document(document_id)
            await db.commit()

            return {
                "status": "success",
                "document_id": str(document_id),
                "chunks_created": document.chunk_count,
            }

        except Exception as e:
            # The service sets document.status = "failed" before re-raising,
            # so commit to persist the error status rather than rolling back.
            try:
                await db.commit()
            except Exception:
                await db.rollback()
            return {"status": "error", "message": str(e)}
