"""RAG Query Service - Fixed pipeline with best-in-class components.

Always uses:
- BGE-M3 triple embedding
- 4-way hybrid retrieval (dense+sparse+BM25+visual with RRF)
- BGE-reranker-v2-m3
- Redis cache
- Parent-child retrieval (returns parent section for broader context)

Retrieval filters use document_id (resolved from KB via join table),
not knowledge_base_id directly.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.knowledge_base import KnowledgeBase, KnowledgeBaseDocument, DocumentChunk
from src.rag.base import Chunk, SearchResult, RAGConfig
from src.rag.factory import RAGFactory

logger = logging.getLogger(__name__)


@dataclass
class RAGQueryResult:
    """Result from a RAG query."""

    query: str
    results: list[SearchResult]
    cached: bool = False
    total_time_ms: float = 0.0
    retrieval_time_ms: float = 0.0
    rerank_time_ms: float = 0.0


class RAGQueryService:
    """Executes RAG queries using the fixed best-in-class pipeline.

    For each query:
    1. Creates pipeline (BGE-M3 + Qdrant + TripleHybridRetriever + BGE-reranker)
    2. Resolves KB IDs → document IDs via join table
    3. Checks Redis cache first
    4. Executes 4-way hybrid retrieval -> BGE reranking
    5. Looks up parent chunks for broader context
    6. Returns results
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._factory = RAGFactory()
        self._pipeline = None

    async def _get_pipeline(self):
        """Get or create the RAG pipeline (singleton per service instance)."""
        if self._pipeline is None:
            config = RAGConfig()
            self._pipeline = await self._factory.create_pipeline(
                config=config,
                qdrant_url=settings.qdrant_url,
                qdrant_api_key=settings.qdrant_api_key or None,
                redis_url=settings.redis_url,
                bm25_loader=self._load_bm25_chunks,
            )
        return self._pipeline

    async def _load_bm25_chunks(self, doc_ids: list[str]) -> list[Chunk]:
        """Load document chunks from PostgreSQL for BM25 indexing.

        Called lazily by the TripleHybridRetriever when it encounters
        document IDs that haven't been loaded into the BM25 index yet.
        """
        from uuid import UUID as _UUID

        uuid_ids = [_UUID(d) for d in doc_ids]
        query = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id.in_(uuid_ids),
                DocumentChunk.is_parent == False,
            )
        )
        result = await self.db.execute(query)
        db_chunks = result.scalars().all()

        return [
            Chunk(
                id=str(dc.id),
                document_id=str(dc.document_id),
                content=dc.content,
                chunk_index=dc.chunk_index or 0,
                page_number=dc.page_number or 0,
                element_type=dc.element_type or "text",
            )
            for dc in db_chunks
        ]

    async def _resolve_document_ids(self, kb_ids: list[UUID]) -> list[str]:
        """Resolve knowledge base IDs to document IDs via the join table."""
        query = (
            select(KnowledgeBaseDocument.document_id)
            .where(KnowledgeBaseDocument.knowledge_base_id.in_(kb_ids))
            .distinct()
        )
        result = await self.db.execute(query)
        return [str(did) for did in result.scalars().all()]

    async def query(
        self,
        query: str,
        knowledge_base_ids: list[UUID],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> RAGQueryResult:
        """Execute a RAG query across one or more knowledge bases.

        Uses the fixed pipeline: BGE-M3 -> 3-way hybrid -> BGE reranker.
        """
        if not knowledge_base_ids:
            return RAGQueryResult(query=query, results=[])

        start = time.time()

        # Resolve KB IDs → document IDs via join table
        doc_ids = await self._resolve_document_ids(knowledge_base_ids)
        if not doc_ids:
            return RAGQueryResult(query=query, results=[])

        # Get the pipeline (fixed config for all KBs)
        pipeline = await self._get_pipeline()

        # Build filter using document IDs (not knowledge_base_id)
        filter_metadata = {
            "document_id": doc_ids,
        }

        # Generate visual query embedding for page-level visual search (ColSmol)
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
                        top_k=5,
                        filter_metadata=filter_metadata,
                    )
            except Exception as e:
                logger.warning("Visual query failed, continuing with text-only retrieval: %s", e)

        # Query the pipeline (handles retrieval + reranking + caching)
        config = RAGConfig()
        query_result = await pipeline.query(
            query=query,
            top_k=top_k or config.top_n,
            filter_metadata=filter_metadata,
            visual_results=visual_results,
        )

        total_time = (time.time() - start) * 1000

        return RAGQueryResult(
            query=query,
            results=query_result.results,
            cached=query_result.cached,
            total_time_ms=total_time,
            retrieval_time_ms=query_result.retrieval_time_ms,
            rerank_time_ms=query_result.rerank_time_ms,
        )

    def format_context(
        self,
        results: list[SearchResult],
        max_tokens: int = 4000,
    ) -> str:
        """Format search results into rich context string for LLM.

        Uses parent content when available for broader context.
        Includes element IDs, page numbers, confidence, section headings,
        and type-specific formatting for all 23 element types.
        """
        if not results:
            return ""

        context_parts = []
        estimated_tokens = 0

        for i, result in enumerate(results, 1):
            chunk = result.chunk
            content = chunk.parent_content or chunk.content
            etype = chunk.element_type or "text"
            meta = chunk.metadata or {}

            # v2 enriched fields
            element_id = meta.get("element_id", "")
            page = chunk.page_number or 0
            confidence = meta.get("confidence")
            headings = meta.get("headings", [])
            label = meta.get("label", etype)

            # Build header line
            header_parts = [f"[Source {i}]"]
            if element_id:
                header_parts.append(f"id={element_id}")
            if page:
                header_parts.append(f"page={page}")
            header_parts.append(f"type={etype}")
            if headings:
                section = " > ".join(headings) if isinstance(headings, list) else str(headings)
                header_parts.append(f"section={section}")
            if confidence is not None and confidence < 0.5:
                header_parts.append("LOW_CONFIDENCE")

            header = " ".join(header_parts)

            # Type-specific formatting
            if etype == "table":
                table_md = meta.get("table_markdown", "")
                display = table_md or content
                num_rows = meta.get("num_rows", "?")
                num_cols = meta.get("num_cols", "?")
                detection = meta.get("detection_method", "")
                type_line = f"Table ({num_rows}x{num_cols})"
                if detection:
                    type_line += f" [{detection}]"
                formatted = f"{header}\n{type_line}\n{display}"

            elif etype in ("figure", "chart", "image"):
                parts = []
                classification = meta.get("classification", "")
                caption = meta.get("caption", "") or meta.get("original_caption", "")
                desc_source = meta.get("description_source", "")
                type_label = etype.title()
                if classification:
                    type_label += f" ({classification})"
                parts.append(type_label)
                if content:
                    parts.append(f"Description: {content}")
                if caption and caption != content:
                    parts.append(f"Caption: {caption}")
                if desc_source:
                    parts.append(f"[{desc_source}]")
                formatted = f"{header}\n" + "\n".join(parts)

            elif etype == "code":
                language = meta.get("language", "")
                code_orig = meta.get("code_original", "")
                display = code_orig or content
                fence = f"```{language}" if language else "```"
                formatted = f"{header}\nCode\n{fence}\n{display}\n```"

            elif etype == "equation":
                formatted = f"{header}\nEquation: ${content}$"

            elif etype == "key_value":
                formatted = f"{header}\nKey-Value\n{content}"

            elif etype == "checkbox":
                checked = meta.get("checked", False)
                mark = "[x]" if checked else "[ ]"
                formatted = f"{header}\nCheckbox: {mark} {content}"

            elif etype == "handwritten":
                conf_warning = ""
                if confidence is not None and confidence < 0.7:
                    conf_warning = " (low OCR confidence — handwritten text)"
                formatted = f"{header}\nHandwritten{conf_warning}\n{content}"

            elif etype == "section_header" or etype == "title":
                level = meta.get("level", 1)
                prefix = "#" * min(level, 6) if isinstance(level, int) else "#"
                formatted = f"{header}\n{prefix} {content}"

            else:
                formatted = f"{header}\n{content}"

            chunk_tokens = len(formatted) // 4
            if estimated_tokens + chunk_tokens > max_tokens:
                break
            context_parts.append(formatted)
            estimated_tokens += chunk_tokens

        return "\n\n".join(context_parts)

    async def _get_knowledge_base(self, kb_id: UUID) -> KnowledgeBase | None:
        """Get a knowledge base by ID."""
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        return result.scalar_one_or_none()
