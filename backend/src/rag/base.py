"""Base classes and interfaces for the RAG system.

All components implement these abstract base classes, making the system
fully pluggable and extensible.

Design Goals:
- Clean interfaces for each component type
- Immutable data classes for thread safety
- Type hints for IDE support and documentation
- Async-first for high concurrency
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import hashlib
import uuid

from src.rag.models import TripleEmbedding


# =============================================================================
# Enums - Fixed to best-in-class defaults (no user choice)
# =============================================================================

# =============================================================================
# Data Classes - Immutable structures for passing data
# =============================================================================

@dataclass(frozen=True)
class Document:
    """A document to be indexed.

    Attributes:
        id: Unique identifier
        content: Full text content
        metadata: Document metadata (source, author, date, etc.)
        file_path: Optional path to source file
        file_type: File type (pdf, docx, txt, etc.)
    """
    id: str
    content: str
    metadata: dict = field(default_factory=dict)
    file_path: Optional[str] = None
    file_type: Optional[str] = None

    @staticmethod
    def generate_id(content: str, file_path: Optional[str] = None) -> str:
        """Generate deterministic ID from content hash."""
        hash_input = f"{file_path or ''}{content[:1000]}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class Chunk:
    """A chunk of text with embedding.

    Attributes:
        id: Unique identifier
        document_id: Parent document ID
        content: Chunk text
        embedding: Triple embedding (None until embedded)
        metadata: Chunk metadata (position, page, section, etc.)
        chunk_index: Position in document
        start_char: Start character offset
        end_char: End character offset
        page_number: Page number in source document
        element_type: Type of document element (text, table, image, etc.)
        bbox: Bounding box dict or None
        parent_chunk_id: ID of parent chunk (for parent-child retrieval)
        parent_content: Content of parent chunk (populated at retrieval time)
    """
    id: str
    document_id: str
    content: str
    embedding: Optional[TripleEmbedding] = None
    metadata: dict = field(default_factory=dict)
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    page_number: int = 0
    element_type: str = "text"
    bbox: Optional[dict] = None
    parent_chunk_id: Optional[str] = None
    parent_content: Optional[str] = None

    @staticmethod
    def generate_id(document_id: str, chunk_index: int, content: str) -> str:
        """Generate deterministic chunk ID."""
        hash_input = f"{document_id}:{chunk_index}:{content[:100]}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]

    def with_embedding(self, embedding: TripleEmbedding) -> "Chunk":
        """Return new Chunk with embedding set."""
        return Chunk(
            id=self.id,
            document_id=self.document_id,
            content=self.content,
            embedding=embedding,
            metadata=self.metadata,
            chunk_index=self.chunk_index,
            start_char=self.start_char,
            end_char=self.end_char,
            page_number=self.page_number,
            element_type=self.element_type,
            bbox=self.bbox,
            parent_chunk_id=self.parent_chunk_id,
            parent_content=self.parent_content,
        )


@dataclass(frozen=True)
class SearchResult:
    """A search result with relevance score.

    Attributes:
        chunk: The matched chunk
        score: Relevance score (0-1, higher is better)
        rank: Position in results (1-based)
        retrieval_method: Which retrieval method found this
        rerank_score: Score after reranking (if applicable)
    """
    chunk: Chunk
    score: float
    rank: int = 0
    retrieval_method: str = "vector"
    rerank_score: Optional[float] = None

    def with_rerank_score(self, score: float, new_rank: int) -> "SearchResult":
        """Return new SearchResult with rerank score."""
        return SearchResult(
            chunk=self.chunk,
            score=self.score,
            rank=new_rank,
            retrieval_method=self.retrieval_method,
            rerank_score=score,
        )


@dataclass
class RAGConfig:
    """Configuration for the RAG pipeline.

    All values are fixed internally - no user-configurable fields.
    The platform uses best-in-class defaults:
    - Docling HybridChunker (structure-aware, ~512 tokens)
    - Late chunking with BGE-M3 (document-context-aware embeddings, zero LLM calls)
    - Parent-child retrieval (search small, return big)
    - BGE-M3 triple embedding (dense+sparse+ColBERT)
    - 4-way hybrid retrieval + RRF fusion (dense+sparse+BM25+visual)
    - BGE-reranker-v2-m3
    - Qdrant + Redis cache
    """
    # Chunking (fixed)
    chunk_size: int = 512                # tokens
    chunk_overlap: int = 50              # tokens
    min_chunk_size: int = 100            # minimum chunk size (chars)

    # Retrieval (fixed)
    top_k: int = 20                      # Candidates to retrieve (more for reranking)
    top_n: int = 5                       # Final results after reranking

    # Parent-child retrieval
    enable_parent_child: bool = True
    parent_chunk_size: int = 2048        # tokens for parent sections

    # Fixed internal values
    embedding_dimension: int = 1024      # BGE-M3 output dim
    cache_ttl_seconds: int = 3600


# =============================================================================
# Abstract Base Classes - Interfaces for pluggable components
# =============================================================================

class BaseChunker(ABC):
    """Abstract base class for text chunkers."""

    def __init__(self, config: RAGConfig):
        self.config = config

    @abstractmethod
    def chunk(self, text: str, metadata: Optional[dict] = None) -> list[Chunk]:
        """Split text into chunks."""
        pass


class BaseEmbedder(ABC):
    """Abstract base class for embedding generators."""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.dimensions = config.embedding_dimension

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate dense embedding for text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate dense embeddings for multiple texts."""
        pass

    async def embed_triple(self, texts: list[str]) -> list[TripleEmbedding]:
        """Generate triple embeddings (dense+sparse+colbert) for texts.

        Default implementation returns dense-only triples.
        Override in BGE-M3 provider for full triple output.
        """
        dense_vecs = await self.embed_batch(texts)
        return [TripleEmbedding(dense=d) for d in dense_vecs]

    async def embed_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Embed all chunks with triple embeddings."""
        texts = [c.content for c in chunks]
        triples = await self.embed_triple(texts)
        return [c.with_embedding(t) for c, t in zip(chunks, triples)]


class BaseVectorStore(ABC):
    """Abstract base class for vector stores."""

    def __init__(self, config: RAGConfig, collection_name: str):
        self.config = config
        self.collection_name = collection_name

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the vector store (create collection/index)."""
        pass

    @abstractmethod
    async def add(self, chunks: list[Chunk]) -> None:
        """Add chunks to the store. Chunks must have TripleEmbedding set."""
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: TripleEmbedding | list[float],
        top_k: int = 10,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search by vector similarity. Accepts TripleEmbedding or dense-only."""
        pass

    @abstractmethod
    async def delete(self, chunk_ids: list[str]) -> None:
        """Delete chunks by ID."""
        pass

    @abstractmethod
    async def delete_by_document(self, document_id: str) -> None:
        """Delete all chunks for a document."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connections and clean up."""
        pass

    async def count(self) -> int:
        """Get total chunk count."""
        return 0

    async def health_check(self) -> bool:
        """Check if store is healthy."""
        return True


class BaseRetriever(ABC):
    """Abstract base class for retrievers."""

    def __init__(self, config: RAGConfig, **kwargs):
        self.config = config

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Retrieve relevant chunks for query."""
        pass


class BaseReranker(ABC):
    """Abstract base class for rerankers."""

    def __init__(self, config: RAGConfig):
        self.config = config

    @abstractmethod
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: Optional[int] = None,
    ) -> list[SearchResult]:
        """Rerank search results."""
        pass


class BaseCache(ABC):
    """Abstract base class for caching."""

    def __init__(self, config: RAGConfig):
        self.config = config

    @abstractmethod
    async def get(
        self,
        key: str,
        query_embedding: Optional[list[float]] = None,
    ) -> Optional[Any]:
        """Get cached value."""
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        query_embedding: Optional[list[float]] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Set cached value."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete cached value."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached values."""
        pass

    async def close(self) -> None:
        """Close connections."""
        pass


# =============================================================================
# Utility Functions
# =============================================================================

def normalize_score(score: float, method: str = "cosine") -> float:
    """Normalize score to 0-1 range."""
    if method == "cosine":
        return max(0.0, min(1.0, score))
    elif method == "euclidean":
        return 1.0 / (1.0 + score)
    elif method == "dot":
        return max(0.0, min(1.0, (score + 1) / 2))
    else:
        return score


def reciprocal_rank_fusion(
    result_lists: list[list[SearchResult]],
    k: int = 60,
    weights: Optional[list[float]] = None,
) -> list[SearchResult]:
    """Combine multiple result lists using Reciprocal Rank Fusion (RRF)."""
    if not result_lists:
        return []

    if weights is None:
        weights = [1.0] * len(result_lists)

    chunk_scores: dict[str, float] = {}
    chunk_map: dict[str, SearchResult] = {}

    for results, weight in zip(result_lists, weights):
        for rank, result in enumerate(results, start=1):
            chunk_id = result.chunk.id
            rrf_score = weight * (1.0 / (k + rank))
            chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + rrf_score
            chunk_map[chunk_id] = result

    sorted_ids = sorted(chunk_scores.keys(), key=lambda x: chunk_scores[x], reverse=True)

    return [
        SearchResult(
            chunk=chunk_map[chunk_id].chunk,
            score=chunk_scores[chunk_id],
            rank=rank,
            retrieval_method="rrf",
        )
        for rank, chunk_id in enumerate(sorted_ids, start=1)
    ]
