"""RAG Pipeline - Orchestrates the full RAG workflow.

Uses fixed best-in-class components:
- Docling HybridChunker (structure-aware, auto-adapts to document type)
- Late chunking with BGE-M3 (document-context-aware embeddings, zero LLM calls)
- Parent-child retrieval (search small, return big)
- BGE-M3 triple embeddings (dense + sparse)
- Qdrant with named vectors
- TripleHybridRetriever (dense + sparse + BM25 + visual with RRF)
- BGE-reranker-v2-m3
- Redis cache
"""

from __future__ import annotations

from typing import Optional, Any
from dataclasses import dataclass, field

from src.rag.base import (
    RAGConfig,
    Document,
    Chunk,
    SearchResult,
    BaseChunker,
    BaseVectorStore,
    BaseRetriever,
    BaseReranker,
    BaseCache,
    BaseEmbedder,
)
from src.rag.models import DocumentStructure, TripleEmbedding


@dataclass
class IndexResult:
    """Result of document indexing."""
    document_id: str
    chunks_created: int
    chunks_indexed: int
    metadata: dict = field(default_factory=dict)


@dataclass
class QueryResult:
    """Result of a RAG query."""
    query: str
    results: list[SearchResult]
    cached: bool = False
    total_time_ms: float = 0.0
    retrieval_time_ms: float = 0.0
    rerank_time_ms: float = 0.0


class RAGPipeline:
    """Main RAG pipeline orchestrating all components.

    Handles:
    1. Document ingestion: element-aware chunking + triple embedding + Qdrant storage
    2. Query processing: triple hybrid retrieval + BGE reranking
    3. Caching: Redis semantic cache
    """

    def __init__(
        self,
        config: RAGConfig,
        chunker: BaseChunker,
        vector_store: BaseVectorStore,
        retriever: BaseRetriever,
        embedder: BaseEmbedder,
        reranker: Optional[BaseReranker] = None,
        cache: Optional[BaseCache] = None,
    ):
        self.config = config
        self.chunker = chunker
        self.vector_store = vector_store
        self.retriever = retriever
        self.embedder = embedder
        self.reranker = reranker
        self.cache = cache

    async def initialize(self) -> None:
        """Initialize all components."""
        await self.vector_store.initialize()

    async def close(self) -> None:
        """Close all connections."""
        await self.vector_store.close()
        if self.cache:
            await self.cache.close()

    async def index_document(
        self,
        document: Document,
        metadata: Optional[dict] = None,
        document_structure: Optional[DocumentStructure] = None,
    ) -> IndexResult:
        """Index a document into the RAG system.

        Uses DoclingHybridChunker for all document types:
        - Structured documents: chunk_structured() respects document structure
        - Plain text: chunk() with token-based recursive splitting

        Args:
            document: Document to index
            metadata: Additional metadata
            document_structure: Optional structured content from Docling

        Returns:
            IndexResult with statistics
        """
        import time
        start = time.time()

        base_metadata = {
            "document_id": document.id,
            **(document.metadata or {}),
            **(metadata or {}),
        }

        # Chunk using DoclingHybridChunker
        if document_structure:
            from src.rag.chunking.docling_hybrid import DoclingHybridChunker
            if isinstance(self.chunker, DoclingHybridChunker):
                chunks = self.chunker.chunk_structured(
                    structure=document_structure,
                    document_id=document.id,
                    base_metadata=base_metadata,
                )
            else:
                # Fallback for any non-Docling chunker
                chunks = self.chunker.chunk(document.content, base_metadata)
        else:
            chunks = self.chunker.chunk(document.content, base_metadata)
            chunks = [
                Chunk(
                    id=Chunk.generate_id(document.id, i, c.content),
                    document_id=document.id,
                    content=c.content,
                    metadata=c.metadata,
                    chunk_index=i,
                    start_char=c.start_char,
                    end_char=c.end_char,
                    page_number=c.page_number,
                    element_type=c.element_type,
                    bbox=c.bbox,
                )
                for i, c in enumerate(chunks)
            ]

        if not chunks:
            return IndexResult(
                document_id=document.id,
                chunks_created=0,
                chunks_indexed=0,
            )

        # Generate triple embeddings with BGE-M3
        chunks = await self.embedder.embed_chunks(chunks)

        # Store in Qdrant with named vectors
        await self.vector_store.add(chunks)

        elapsed = (time.time() - start) * 1000

        return IndexResult(
            document_id=document.id,
            chunks_created=len(chunks),
            chunks_indexed=len(chunks),
            metadata={
                "processing_time_ms": elapsed,
                "avg_chunk_size": sum(len(c.content) for c in chunks) / len(chunks),
                "element_types": list(set(c.element_type for c in chunks)),
            },
        )

    async def index_documents(
        self,
        documents: list[Document],
        metadata: Optional[dict] = None,
    ) -> list[IndexResult]:
        """Index multiple documents."""
        results = []
        for doc in documents:
            result = await self.index_document(doc, metadata)
            results.append(result)
        return results

    async def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[dict] = None,
        use_cache: bool = True,
        use_reranker: bool = True,
        visual_results: Optional[list[SearchResult]] = None,
    ) -> QueryResult:
        """Query the RAG system.

        Always uses:
        1. BGE-M3 triple embedding for the query
        2. TripleHybridRetriever (dense+sparse+BM25 with RRF)
        3. BGE-reranker-v2-m3 for reranking

        Args:
            query: Search query
            top_k: Number of final results (after reranking)
            filter_metadata: Optional metadata filters
            use_cache: Whether to use Redis cache
            use_reranker: Whether to apply reranking

        Returns:
            QueryResult with results and timing
        """
        import time
        start = time.time()
        top_k = top_k or self.config.top_n  # Final count after reranking

        # Embed query once — reused for cache lookup, retrieval, and cache update
        triples = await self.embedder.embed_triple([query])
        query_triple = triples[0]
        dense_embedding = query_triple.dense

        # Check cache
        if use_cache and self.cache:
            cached = await self.cache.get(query, dense_embedding)
            if cached:
                return QueryResult(
                    query=query,
                    results=cached,
                    cached=True,
                    total_time_ms=(time.time() - start) * 1000,
                )

        # Retrieve (TripleHybridRetriever handles all arms)
        retrieval_start = time.time()
        retrieval_top_k = self.config.top_k  # Get more candidates for reranking
        results = await self.retriever.retrieve(
            query=query,
            top_k=retrieval_top_k,
            filter_metadata=filter_metadata,
            precomputed_triple=query_triple,
            visual_results=visual_results,
        )
        retrieval_time = (time.time() - retrieval_start) * 1000

        # Rerank with BGE-reranker-v2-m3
        rerank_time = 0.0
        if self.reranker and use_reranker and results:
            rerank_start = time.time()
            results = await self.reranker.rerank(query, results, top_k)
            rerank_time = (time.time() - rerank_start) * 1000

        # Trim to final count
        results = results[:top_k]

        # Update cache
        if use_cache and self.cache and results:
            await self.cache.set(query, results, dense_embedding)

        total_time = (time.time() - start) * 1000

        return QueryResult(
            query=query,
            results=results,
            cached=False,
            total_time_ms=total_time,
            retrieval_time_ms=retrieval_time,
            rerank_time_ms=rerank_time,
        )

    async def delete_document(self, document_id: str) -> int:
        """Delete a document and its chunks."""
        return await self.vector_store.delete_by_document(document_id)

    async def stats(self) -> dict:
        """Get pipeline statistics."""
        stats = {
            "config": {
                "chunking": "Docling HybridChunker (structure-aware)",
                "embedding": "Late chunking with BGE-M3 (document-context-aware)",
                "parent_child_retrieval": self.config.enable_parent_child,
                "top_k": self.config.top_k,
                "top_n": self.config.top_n,
                "embedding_dimension": self.config.embedding_dimension,
            },
            "components": {
                "chunker": "Docling HybridChunker",
                "embedder": "BGE-M3 ONNX int8 (late chunking)",
                "retriever": "TripleHybridRetriever (dense+sparse+BM25+visual)",
                "reranker": "BGE-reranker-v2-m3",
                "vector_store": "Qdrant (named vectors)",
                "cache": "Redis" if self.cache else "None",
            },
            "vector_store": {
                "total_chunks": await self.vector_store.count(),
            },
        }

        if self.cache:
            stats["cache"] = await self.cache.stats()

        return stats
