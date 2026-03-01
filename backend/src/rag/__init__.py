"""RAG (Retrieval-Augmented Generation) Module.

A fully automated RAG system using best-in-class open-source components:
- Docling HybridChunker (structure-aware chunking, auto-adapts)
- Late chunking with BGE-M3 (document-context-aware embeddings, zero LLM calls)
- Parent-child retrieval (search small, return big — stored in Qdrant payload)
- BGE-M3 triple embedding (dense+sparse+ColBERT)
- BGE-reranker-v2-m3 (reranker)
- 3-way hybrid retrieval (dense+sparse+BM25 with RRF)
- Qdrant with named vectors (vector store)
- Redis (cache)

No user-configurable RAG fields. The platform handles everything.

Architecture:
    Document -> Docling -> HybridChunker -> Late Chunking (BGE-M3) -> Qdrant
    Query -> BGE-M3 -> TripleHybridRetriever -> BGE Reranker -> Results
"""

from src.rag.base import (
    # Base classes
    BaseChunker,
    BaseVectorStore,
    BaseRetriever,
    BaseReranker,
    BaseCache,
    BaseEmbedder,
    # Data classes
    Document,
    Chunk,
    SearchResult,
    RAGConfig,
)
from src.rag.models import (
    ElementType,
    BoundingBox,
    TripleEmbedding,
    DocumentStructure,
)
from src.rag.pipeline import RAGPipeline, IndexResult, QueryResult
from src.rag.factory import RAGFactory, create_rag_pipeline

# Primary chunker
from src.rag.chunking import DoclingHybridChunker

# Vector stores
from src.rag.vectorstores import (
    QdrantStore,
)

# Retrieval strategies
from src.rag.retrieval import (
    TripleHybridRetriever,
    BM25Retriever,
)

# Caching
from src.rag.cache import (
    RedisSemanticCache,
)

__all__ = [
    # Base classes
    "BaseChunker",
    "BaseVectorStore",
    "BaseRetriever",
    "BaseReranker",
    "BaseCache",
    "BaseEmbedder",
    # Data classes
    "Document",
    "Chunk",
    "SearchResult",
    "RAGConfig",
    "TripleEmbedding",
    "BoundingBox",
    "DocumentStructure",
    "ElementType",
    # Main classes
    "RAGPipeline",
    "RAGFactory",
    "create_rag_pipeline",
    "IndexResult",
    "QueryResult",
    # Chunker
    "DoclingHybridChunker",
    # Vector stores
    "QdrantStore",
    # Retrievers
    "TripleHybridRetriever",
    "BM25Retriever",
    # Caching
    "RedisSemanticCache",
]
