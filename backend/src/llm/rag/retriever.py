"""Retriever for RAG using Qdrant vector database."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge_base import DocumentChunk, Document, KnowledgeBase, KnowledgeBaseDocument
from src.llm.rag.embeddings import EmbeddingService
from src.core.config import settings


@dataclass
class RetrievalResult:
    """Result from retrieval."""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    metadata: dict


class Retriever:
    """Retrieve relevant chunks from knowledge bases using Qdrant vector similarity."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()
        self._qdrant = None

    async def _get_qdrant(self):
        """Lazy-initialize QdrantStore."""
        if self._qdrant is None:
            from src.rag.vectorstores.qdrant import QdrantStore
            from src.rag.base import RAGConfig

            config = RAGConfig()
            self._qdrant = QdrantStore(
                config=config,
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
            )
            await self._qdrant.initialize()
        return self._qdrant

    async def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[UUID],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[RetrievalResult]:
        """Retrieve relevant chunks for a query.

        Args:
            query: The search query
            knowledge_base_ids: List of knowledge base IDs to search
            top_k: Number of results to return
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of RetrievalResult ordered by relevance
        """
        if not knowledge_base_ids:
            return []

        # Generate query embedding
        query_embedding = await self.embedding_service.embed_text(query)

        # Resolve KB IDs → document IDs via join table
        qdrant = await self._get_qdrant()
        doc_id_query = (
            select(KnowledgeBaseDocument.document_id)
            .where(KnowledgeBaseDocument.knowledge_base_id.in_(knowledge_base_ids))
            .distinct()
        )
        doc_id_result = await self.db.execute(doc_id_query)
        doc_ids = [str(did) for did in doc_id_result.scalars().all()]
        if not doc_ids:
            return []

        filter_metadata = {
            "document_id": doc_ids,
        }

        search_results = await qdrant.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
            score_threshold=score_threshold if score_threshold > 0 else None,
        )

        # Convert to RetrievalResult
        results = []
        for sr in search_results:
            chunk = sr.chunk
            try:
                chunk_id = UUID(chunk.id)
            except (ValueError, AttributeError):
                continue

            doc_id_str = chunk.metadata.get("document_id") or chunk.document_id
            try:
                document_id = UUID(str(doc_id_str))
            except (ValueError, AttributeError):
                continue

            results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content=chunk.content,
                    score=float(sr.score),
                    metadata=chunk.metadata,
                )
            )

        return results

    async def retrieve_with_context(
        self,
        query: str,
        knowledge_base_ids: list[UUID],
        top_k: int = 5,
        context_chunks: int = 1,
        score_threshold: float = 0.0,
    ) -> list[RetrievalResult]:
        """Retrieve chunks with surrounding context.

        Gets neighboring chunks to provide more context.

        Args:
            query: The search query
            knowledge_base_ids: List of knowledge base IDs to search
            top_k: Number of results to return
            context_chunks: Number of chunks before/after to include
            score_threshold: Minimum similarity score

        Returns:
            List of RetrievalResult with expanded context
        """
        # First get the base results
        base_results = await self.retrieve(
            query=query,
            knowledge_base_ids=knowledge_base_ids,
            top_k=top_k,
            score_threshold=score_threshold,
        )

        if not base_results or context_chunks == 0:
            return base_results

        # Get surrounding chunks for each result
        expanded_results = []
        seen_chunks = set()

        for result in base_results:
            if result.chunk_id in seen_chunks:
                continue

            # Get chunk with its neighbors
            expanded = await self._get_chunk_with_context(
                result.document_id,
                result.chunk_id,
                result.score,
                context_chunks,
            )

            for chunk in expanded:
                if chunk.chunk_id not in seen_chunks:
                    seen_chunks.add(chunk.chunk_id)
                    expanded_results.append(chunk)

        return expanded_results[:top_k]

    async def _get_chunk_with_context(
        self,
        document_id: UUID,
        chunk_id: UUID,
        base_score: float,
        context_size: int,
    ) -> list[RetrievalResult]:
        """Get a chunk with its surrounding context chunks."""
        # Get the current chunk's index
        current_chunk = await self.db.get(DocumentChunk, chunk_id)
        if not current_chunk:
            return []

        current_index = current_chunk.chunk_index

        # Get surrounding chunks
        start_index = max(0, current_index - context_size)
        end_index = current_index + context_size

        query = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.chunk_index >= start_index)
            .where(DocumentChunk.chunk_index <= end_index)
            .order_by(DocumentChunk.chunk_index)
        )

        result = await self.db.execute(query)
        chunks = result.scalars().all()

        return [
            RetrievalResult(
                chunk_id=chunk.id,
                document_id=document_id,
                content=chunk.content,
                score=base_score if chunk.id == chunk_id else base_score * 0.9,
                metadata=chunk.meta_data,
            )
            for chunk in chunks
        ]

    def format_context(
        self,
        results: list[RetrievalResult],
        max_tokens: int = 4000,
    ) -> str:
        """Format retrieval results into context string.

        Args:
            results: List of retrieval results
            max_tokens: Maximum tokens for context

        Returns:
            Formatted context string
        """
        if not results:
            return ""

        context_parts = []
        estimated_tokens = 0

        for i, result in enumerate(results, 1):
            # Rough token estimate: 1 token ~ 4 chars
            chunk_tokens = len(result.content) // 4

            if estimated_tokens + chunk_tokens > max_tokens:
                break

            context_parts.append(f"[Source {i}]\n{result.content}")
            estimated_tokens += chunk_tokens

        return "\n\n".join(context_parts)
