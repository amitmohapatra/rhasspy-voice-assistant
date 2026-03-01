"""Embedding generation tasks.

Uses the inference service for BGE-M3 triple embeddings (dense+sparse+ColBERT).
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from src.worker import celery_app


def _create_session_factory():
    """Create a fresh async engine + session factory for Celery tasks."""
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


@celery_app.task(bind=True, name="src.tasks.embedding.generate_embeddings")
def generate_embeddings(self, chunk_ids: list[str]) -> dict:
    """Generate BGE-M3 triple embeddings for chunks and store in Qdrant.

    This is useful for reprocessing or updating embeddings.
    """
    from src.clients.inference_client import reset_inference_client
    reset_inference_client()

    return asyncio.run(_generate_embeddings_async([UUID(cid) for cid in chunk_ids]))


async def _generate_embeddings_async(chunk_ids: list[UUID]) -> dict:
    """Async implementation of embedding generation."""
    from sqlalchemy import select

    from src.core.config import settings
    from src.models.knowledge_base import DocumentChunk
    from src.clients.inference_client import get_inference_client
    from src.rag.vectorstores.qdrant import QdrantStore
    from src.rag.base import RAGConfig, Chunk as RAGChunk

    SessionLocal = _create_session_factory()

    async with SessionLocal() as db:
        # Get chunks
        query = select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
        result = await db.execute(query)
        chunks = result.scalars().all()

        if not chunks:
            return {"status": "error", "message": "No chunks found"}

        try:
            # Generate BGE-M3 triple embeddings via inference service
            client = get_inference_client()
            chunk_texts = [c.content for c in chunks]
            triples = await client.embed_triple(chunk_texts)

            # Build RAG chunks with embeddings
            rag_chunks = []
            for chunk, triple in zip(chunks, triples):
                rag_chunks.append(RAGChunk(
                    id=str(chunk.id),
                    document_id=str(chunk.document_id),
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    element_type=chunk.element_type,
                    metadata=chunk.meta_data or {},
                    embedding=triple,
                ))

            # Store in Qdrant
            config = RAGConfig()
            qdrant = QdrantStore(
                config=config,
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
            )
            await qdrant.initialize()
            await qdrant.add(rag_chunks)

            return {
                "status": "success",
                "chunks_updated": len(chunks),
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}


@celery_app.task(bind=True, name="src.tasks.embedding.reindex_knowledge_base")
def reindex_knowledge_base(self, knowledge_base_id: str) -> dict:
    """Reindex all documents in a knowledge base.

    Regenerates all BGE-M3 triple embeddings and stores in Qdrant.
    """
    from src.clients.inference_client import reset_inference_client
    reset_inference_client()

    return asyncio.run(_reindex_knowledge_base_async(UUID(knowledge_base_id)))


async def _reindex_knowledge_base_async(knowledge_base_id: UUID) -> dict:
    """Async implementation of knowledge base reindexing."""
    from sqlalchemy import select

    from src.core.config import settings
    from src.models.knowledge_base import KnowledgeBase, KnowledgeBaseDocument, Document, DocumentChunk
    from src.clients.inference_client import get_inference_client
    from src.rag.vectorstores.qdrant import QdrantStore
    from src.rag.base import RAGConfig, Chunk as RAGChunk

    SessionLocal = _create_session_factory()

    async with SessionLocal() as db:
        # Get knowledge base
        kb_query = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
        kb_result = await db.execute(kb_query)
        knowledge_base = kb_result.scalar_one_or_none()

        if not knowledge_base:
            return {"status": "error", "message": "Knowledge base not found"}

        try:
            # Update status
            knowledge_base.status = "reindexing"
            await db.flush()

            # Initialize inference client
            client = get_inference_client()

            # Initialize Qdrant
            config = RAGConfig()
            qdrant = QdrantStore(
                config=config,
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
            )
            await qdrant.initialize()

            # Get all completed documents via join table
            doc_query = (
                select(Document)
                .join(KnowledgeBaseDocument, KnowledgeBaseDocument.document_id == Document.id)
                .where(
                    KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
                    Document.status == "completed",
                )
            )
            doc_result = await db.execute(doc_query)
            documents = doc_result.scalars().all()

            total_chunks = 0

            for document in documents:
                # Get chunks for this document
                chunk_query = select(DocumentChunk).where(
                    DocumentChunk.document_id == document.id
                ).order_by(DocumentChunk.chunk_index)
                chunk_result = await db.execute(chunk_query)
                chunks = chunk_result.scalars().all()

                if not chunks:
                    continue

                # Delete old vectors from Qdrant
                await qdrant.delete_by_document(str(document.id))

                # Generate new BGE-M3 triple embeddings in batches
                batch_size = 100
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i : i + batch_size]
                    texts = [c.content for c in batch]
                    triples = await client.embed_triple(texts)

                    rag_chunks = []
                    for chunk, triple in zip(batch, triples):
                        rag_chunks.append(RAGChunk(
                            id=str(chunk.id),
                            document_id=str(document.id),
                            content=chunk.content,
                            chunk_index=chunk.chunk_index,
                            page_number=chunk.page_number,
                            element_type=chunk.element_type,
                            metadata={
                                **(chunk.meta_data or {}),
                                "document_id": str(document.id),
                                "user_id": str(document.uploaded_by) if document.uploaded_by else None,
                            },
                            embedding=triple,
                        ))

                    await qdrant.add(rag_chunks)
                    total_chunks += len(batch)

            # Update status
            knowledge_base.status = "active"
            await db.commit()

            return {
                "status": "success",
                "knowledge_base_id": str(knowledge_base_id),
                "documents_processed": len(documents),
                "chunks_reindexed": total_chunks,
            }

        except Exception as e:
            knowledge_base.status = "error"
            await db.commit()
            return {"status": "error", "message": str(e)}
