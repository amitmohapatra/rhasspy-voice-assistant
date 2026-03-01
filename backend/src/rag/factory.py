"""RAG Factory - Creates configured RAG pipelines.

All pipelines use fixed best-in-class components:
- Docling HybridChunker (structure-aware, auto-adapts)
- Late chunking with BGE-M3 (document-context-aware, zero LLM calls)
- Qdrant with named vectors (vector store)
- TripleHybridRetriever (dense+sparse+BM25)
- BGE-reranker-v2-m3 (reranker) — via inference service
- Redis (cache)

No user-configurable fields.
"""

from __future__ import annotations

from typing import Optional, Callable, Awaitable
import logging

from src.rag.base import (
    RAGConfig,
    BaseChunker,
    BaseEmbedder,
    BaseReranker,
    Chunk,
    SearchResult,
)
from src.rag.models import TripleEmbedding
from src.rag.pipeline import RAGPipeline

# Type alias for the BM25 loader callback
BM25Loader = Callable[[list[str]], Awaitable[list[Chunk]]]

logger = logging.getLogger(__name__)


# ============================================================================
# Remote wrappers — delegate ML inference to the inference service
# ============================================================================

class RemoteEmbedder(BaseEmbedder):
    """Embedder that delegates to the inference service via HTTP."""

    def __init__(self, config: RAGConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from src.clients.inference_client import get_inference_client
            self._client = get_inference_client()
        return self._client

    async def embed(self, text: str) -> list[float]:
        triples = await self._get_client().embed_triple([text])
        return triples[0].dense

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        triples = await self._get_client().embed_triple(texts)
        return [t.dense for t in triples]

    async def embed_triple(self, texts: list[str]) -> list[TripleEmbedding]:
        return await self._get_client().embed_triple(texts)


class RemoteReranker(BaseReranker):
    """Reranker that delegates to the inference service via HTTP."""

    def __init__(self, config: RAGConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from src.clients.inference_client import get_inference_client
            self._client = get_inference_client()
        return self._client

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: Optional[int] = None,
    ) -> list[SearchResult]:
        if not results:
            return []

        top_k = top_k or self.config.top_n or len(results)
        client = self._get_client()

        documents = [
            {"id": r.chunk.id, "content": r.chunk.content}
            for r in results
        ]

        ranked = await client.rerank(query, documents, top_k)

        # Map ranked results back to SearchResult objects
        chunk_map = {r.chunk.id: r for r in results}
        reranked = []
        for rank, doc in enumerate(ranked, 1):
            original = chunk_map.get(doc["id"])
            if original:
                reranked.append(SearchResult(
                    chunk=original.chunk,
                    score=doc["score"],
                    rank=rank,
                    retrieval_method=f"{original.retrieval_method}+bge",
                    rerank_score=doc["score"],
                ))

        return reranked


class RAGFactory:
    """Factory for creating configured RAG pipelines.

    All components are hardcoded to best-in-class defaults.
    Embedding and reranking are delegated to the inference service.
    """

    async def create_pipeline(
        self,
        config: Optional[RAGConfig] = None,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        redis_url: Optional[str] = None,
        collection_name: str = "chunks",
        embedder: Optional[BaseEmbedder] = None,
        bm25_loader: Optional[BM25Loader] = None,
    ) -> RAGPipeline:
        """Create a configured RAG pipeline with fixed components.

        Args:
            config: Optional RAG configuration (all defaults if None)
            qdrant_url: Qdrant server URL
            qdrant_api_key: Qdrant API key
            redis_url: Redis URL for caching
            collection_name: Qdrant collection name
            embedder: Optional custom embedder (default: RemoteEmbedder)

        Returns:
            Configured RAGPipeline
        """
        config = config or RAGConfig()

        # Create chunker (Docling HybridChunker)
        chunker = self._create_chunker(config)

        # Create embedder (remote BGE-M3 via inference service)
        if embedder is None:
            embedder = self._create_embedder(config)

        # Create vector store (Qdrant with named vectors)
        vector_store = self._create_vector_store(
            config=config,
            qdrant_url=qdrant_url or "http://localhost:6333",
            qdrant_api_key=qdrant_api_key,
            collection_name=collection_name,
        )

        # Create retriever (TripleHybridRetriever)
        retriever = self._create_retriever(config, vector_store, embedder, bm25_loader)

        # Create reranker (remote BGE-reranker via inference service)
        reranker = self._create_reranker(config)

        # Create cache (Redis)
        cache = None
        if redis_url:
            cache = self._create_cache(config, redis_url)

        # Initialize vector store (chunks collection; page_images only if ColSmol enabled)
        await vector_store.initialize()
        from src.core.config import settings as app_settings
        if app_settings.colsmol_enabled:
            await vector_store.initialize_page_images()

        return RAGPipeline(
            config=config,
            chunker=chunker,
            vector_store=vector_store,
            retriever=retriever,
            embedder=embedder,
            reranker=reranker,
            cache=cache,
        )

    def _create_chunker(self, config: RAGConfig) -> BaseChunker:
        """Create Docling HybridChunker."""
        from src.rag.chunking.docling_hybrid import DoclingHybridChunker
        return DoclingHybridChunker(config)

    def _create_embedder(self, config: RAGConfig) -> BaseEmbedder:
        """Create remote embedder that calls the inference service."""
        return RemoteEmbedder(config)

    def _create_vector_store(
        self,
        config: RAGConfig,
        qdrant_url: str,
        qdrant_api_key: Optional[str],
        collection_name: str,
    ):
        """Create Qdrant vector store with named vectors."""
        from src.rag.vectorstores.qdrant import QdrantStore

        return QdrantStore(
            config=config,
            url=qdrant_url,
            api_key=qdrant_api_key,
            collection_name=collection_name,
        )

    def _create_retriever(self, config, vector_store, embedder, bm25_loader=None):
        """Create TripleHybridRetriever."""
        from src.rag.retrieval.hybrid import TripleHybridRetriever

        return TripleHybridRetriever(
            config=config,
            vector_store=vector_store,
            embedder=embedder,
            bm25_loader=bm25_loader,
        )

    def _create_reranker(self, config):
        """Create remote reranker that calls the inference service."""
        return RemoteReranker(config=config)

    def _create_cache(self, config, redis_url):
        """Create Redis cache."""
        from src.rag.cache import RedisSemanticCache

        return RedisSemanticCache(
            config=config,
            redis_url=redis_url,
            ttl=config.cache_ttl_seconds,
        )


async def create_rag_pipeline(
    qdrant_url: Optional[str] = None,
    qdrant_api_key: Optional[str] = None,
    redis_url: Optional[str] = None,
    config: Optional[RAGConfig] = None,
    bm25_loader: Optional[BM25Loader] = None,
    **kwargs,
) -> RAGPipeline:
    """Convenience function to create a RAG pipeline.

    All components are fixed to best-in-class defaults.
    """
    factory = RAGFactory()

    if config is None:
        config = RAGConfig()

    return await factory.create_pipeline(
        config=config,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        redis_url=redis_url,
        bm25_loader=bm25_loader,
        **kwargs,
    )
