"""4-way hybrid retrieval: dense + sparse (from Qdrant) + BM25 + visual with RRF fusion.

This is the sole retrieval strategy for the platform.

Weights: dense=0.35, sparse=0.25, BM25=0.20, visual=0.20.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable, Awaitable

from src.rag.base import (
    BaseRetriever,
    BaseVectorStore,
    BaseEmbedder,
    Chunk,
    SearchResult,
    RAGConfig,
    reciprocal_rank_fusion,
)
from src.rag.models import TripleEmbedding
from src.rag.retrieval.bm25 import BM25Retriever

logger = logging.getLogger(__name__)

# Type alias for the BM25 loader callback
BM25Loader = Callable[[list[str]], Awaitable[list[Chunk]]]


class TripleHybridRetriever(BaseRetriever):
    """4-way hybrid retriever: dense + sparse + BM25 + visual with RRF fusion.

    The sole retriever for the platform. Combines:
    1. Dense semantic search (from Qdrant named vector "dense")
    2. Sparse lexical search (from Qdrant named vector "sparse")
    3. BM25 keyword search (in-memory, lazily loaded from DB per query)
    4. Visual page search (ColSmol-256M multi-vector MaxSim, optional)

    Dense + sparse are handled by QdrantStore.search() when given a TripleEmbedding.
    BM25 runs separately. Visual results are passed in from the caller.
    All results are fused via RRF.
    """

    def __init__(
        self,
        config: RAGConfig,
        vector_store: BaseVectorStore,
        embedder: BaseEmbedder,
        bm25_retriever: Optional[BM25Retriever] = None,
        bm25_loader: Optional[BM25Loader] = None,
        dense_weight: float = 0.35,
        sparse_weight: float = 0.25,
        bm25_weight: float = 0.20,
        visual_weight: float = 0.20,
        rrf_k: int = 60,
    ):
        super().__init__(config)
        self.vector_store = vector_store
        self.embedder = embedder
        self.bm25_retriever = bm25_retriever or BM25Retriever(config)
        self.bm25_loader = bm25_loader
        self._bm25_loaded_doc_ids: set[str] = set()
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.bm25_weight = bm25_weight
        self.visual_weight = visual_weight
        self.rrf_k = rrf_k

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[dict] = None,
        precomputed_triple: Optional[TripleEmbedding] = None,
        visual_results: Optional[list[SearchResult]] = None,
    ) -> list[SearchResult]:
        """Retrieve using 4-way hybrid search.

        1. Embed query with BGE-M3 triple mode (or use precomputed)
        2. Search Qdrant with dense+sparse (fused internally by QdrantStore)
        3. Search BM25 in-memory
        4. Fuse all results via RRF (including visual arm if provided)
        """
        top_k = top_k or self.config.top_k
        retrieval_k = top_k * 3

        # Use precomputed triple if provided (avoids double embedding)
        if precomputed_triple is not None:
            query_triple = precomputed_triple
        else:
            triples = await self.embedder.embed_triple([query])
            query_triple = triples[0]

        # Qdrant search (dense + sparse fused internally)
        qdrant_results = await self.vector_store.search(
            query_embedding=query_triple,
            top_k=retrieval_k,
            filter_metadata=filter_metadata,
        )

        # Lazily load BM25 chunks from DB for the queried documents
        if self.bm25_loader and filter_metadata:
            doc_ids = filter_metadata.get("document_id")
            if isinstance(doc_ids, list):
                missing = [d for d in doc_ids if d not in self._bm25_loaded_doc_ids]
                if missing:
                    try:
                        new_chunks = await self.bm25_loader(missing)
                        if new_chunks:
                            self.bm25_retriever.add_chunks(new_chunks)
                        self._bm25_loaded_doc_ids.update(missing)
                    except Exception as e:
                        logger.warning("BM25 chunk loading failed: %s", e)

        # BM25 search
        bm25_results = await self.bm25_retriever.retrieve(
            query=query,
            top_k=retrieval_k,
            filter_metadata=filter_metadata,
        )

        # Build result lists and weights for RRF
        result_lists = [qdrant_results, bm25_results]
        qdrant_weight = self.dense_weight + self.sparse_weight
        weights = [qdrant_weight, self.bm25_weight]

        # Visual arm (4th, optional — only when visual results provided)
        if visual_results:
            result_lists.append(visual_results)
            weights.append(self.visual_weight)

        # Fuse all results via RRF
        fused = reciprocal_rank_fusion(
            result_lists=result_lists,
            weights=weights,
            k=self.rrf_k,
        )

        return fused[:top_k]
